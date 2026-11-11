# EdgeVPN (astroapps) → new-api 代理池对接指南

> 面向对接会话。本仓库只负责还原节点与协议，线上决策由对接方做。
> 先读《逆向报告》§8 合规：节点为第三方商业资源，研究/自用范围内使用。

---

## 1. 一句话链路

```
avapi getNewServers ──> AES-CBC 解密 ──> 稳定性筛选 ──> sing-box 每节点一个 socks ──> new-api
   (已打通)              (已打通)          (6轮HTTPS204)    (127.0.0.1:24001+i)      (TRYINGOPEN_PROXY_FILE)
```

## 2. 为什么必须经过 sing-box

节点是 **Shadowsocks（chacha20-ietf-poly1305）**，new-api 只会说 HTTP/SOCKS5，中间必须有一个本地转换层。

| 方案 | 做法 | 评价 |
|---|---|---|
| **A. sing-box 单进程多 socks**（本仓库已实现） | 一个 `sing-box run`，`inbounds[]` 每节点一个 socks + `route.rules.inbound→outbound` 逐条绑定 | 单进程、内存 ~35 MB、已验证端口↔节点对应正确 |
| B. xray 多入站 | 同样可行，但 xray 不支持 v2ray-plugin 出站（3 台 v2ray 节点用不了） | 有协议缺口 |
| C. 一节点一进程 | N 个进程，资源浪费 | 不推荐 |

本仓库的 `tools/pool_serve.py` 就是方案 A：读 `data/stable_nodes.json`，生成 sing-box 配置，每节点一个 socks 监听，每 5 分钟探活后重写 `data/proxies.txt`。

## 3. 落地步骤

### 3.1 准备节点

```powershell
# 1) 收割（每次都会覆盖 data/servers_decrypted.json）
python tools\harvest_fastvpn.py ./data

# 2) 一级测活（隔离 sing-box，端口 22001+，不碰系统代理）
python tools\probe_pool.py data\singbox_all_nodes.json data\probe_results.json

# 3) 稳定性采样（6 轮 HTTPS 204，端口 22001+）
python tools\stability.py data\nodes_live.json data\stability.json

# 4) 生成入池子集（成功率 >=60% 且 avg RTT <3 s）
python -c "import json;s={x['tag']:x for x in json.load(open('data/stability.json'))};n=[x for x in json.load(open('data/nodes_live.json')) if x.get('live') and s.get(x['tag'],{}).get('rate',0)>=60 and (s[x['tag']]['rtt_avg'] or 9e9)<3000];json.dump(n,open('data/stable_nodes.json','w'),ensure_ascii=False,indent=1);print(len(n))"
```

### 3.2 起常驻池

```powershell
python tools\pool_serve.py --interval 300
```

- 监听 `127.0.0.1:24001..24002`（当前 2 台）
- 每轮探活后**整体覆写** `data/proxies.txt`，内容：

```
socks5://127.0.0.1:24001
socks5://127.0.0.1:24002
```

- `data/port_map.json` 保留 `端口 ↔ 城市 ↔ 入口 IP`

### 3.3 接入 new-api

```bash
# common/proxy_url.go 白名单: http / https / socks5 / socks5h
export TRYINGOPEN_PROXY_FILE=/abs/path/to/EdgeVPN-ProxyPool/data/proxies.txt

# 热更新（不重启容器）
curl -X POST http://<new-api>/api/twoapi_panel/proxy_pool/reload
```

关键事实（源码核对，非猜测）：

| 项 | 事实 |
|---|---|
| 解析方式 | 逐行整行 `url.Parse`，**只跳过 `#` 开头的整行** ⇒ 不支持行尾注释 |
| 协议白名单 | `http` / `https` / `socks5` / `socks5h` |
| 卡片命名 | `filepath.Base(file)` ⇒ 一个池子一个文件名就独立成卡 |
| Docker 注意 | 容器内 `127.0.0.1` 指容器自身；要么同 network namespace，要么改宿主可达 IP |
| 刷新 | 文件被覆写后调用 `/proxy_pool/reload`，无需重启 |

## 4. 池质量口径

只报实测数据，不报厂商自报。当前快照（2026-11-11）：

| 节点 | 6 轮 HTTPS 成功率 | RTT avg |
|---|---|---|
| Los Angeles II | 100% | 198 ms |
| Montreal II | 100% | 646 ms |
| Barcelona II | 67% | 3557 ms |
| Dallas II | 33% | 4788 ms |
| Ashburn II | 17% | 2718 ms |
| Amsterdam II | 0% | — |

入池阈值：成功率 ≥60% **且** avg RTT <3 s。Barcelona 虽 67% 但 3.5 s 延迟，被阈值挡掉。

带宽未取得有效样本：节点出口对 `speed.cloudflare.com` / `leaseweb` / `tele2` / `thinkbroadband` 的 443 握手全部超时。

## 5. 运维要点

- **不要用 `curl --socks5` 验证**：本机 curl 未编 SOCKS 时会静默直连并返回 200（假阳性）。用 `tools/probe_pool.py` 里的自写 SOCKS5 客户端。
- **测活前查端口占用**：`netstat -ano | findstr :2400`，否则探针会打到别的进程上。
- **Windows 控制台 GBK**：脚本内 `print` 带 emoji 会在被 `subprocess` 拉起时静默失败，统一 `PYTHONIOENCODING=utf-8`。
- **节点会漂**：`avapi` 每次返回的节点集合与凭证都会变；`pool_serve.py` 的周期探活是必要的，不是可选。

## 6. 已知不适用

- 3 台 `v2ray` 节点实为 **SS + v2ray-plugin(ws+tls)**，sing-box 支持但需要 `plugin` + `plugin_opts`，本仓库 `singbox_all_nodes.json` 已带上；本次一级 TLS 握手未通，未入池。
- 34 台 OpenVPN 节点是 **UDP + tls-crypt、证书内嵌、无 auth-user-pass**，TCP 探测无意义，需要真实 openvpn 客户端才能判定；本仓库不做转换（openvpn → socks5 需要 tun2socks，链路更长）。
