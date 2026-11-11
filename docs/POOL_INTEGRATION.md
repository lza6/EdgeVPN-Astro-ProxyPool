# 池接入说明

产物：`data/proxies.txt`（每行一个 `socks5://127.0.0.1:<port>`）。

## 本地常驻

```bash
python tools/pool_serve.py --interval 300
```

每节点一个 sing-box socks 入站（127.0.0.1:24001 起），每 5 分钟对全部节点做一次 gstatic 204 探活，只把通过的写入 `proxies.txt`；`data/port_map.json` 保留端口 ↔ 城市 ↔ 入口 IP 的对应关系。

只监听回环，不注册系统代理、不修改环境变量、不接管 DNS。本机 v2rayN 的 10808/10809 完全不受影响。

## 接入 new-api

`common/proxy_url.go` 白名单为 `http` / `https` / `socks5` / `socks5h`。把 `proxies.txt` 的路径写进 `TRYINGOPEN_PROXY_FILE`（逗号分隔可多文件，解析是逐行整行 `url.Parse`，不支持行尾注释）。

```bash
export TRYINGOPEN_PROXY_FILE=/abs/path/to/data/proxies.txt
# 热更新
curl -X POST http://<new-api>/api/twoapi_panel/proxy_pool/reload
```

来源卡片名取 `filepath.Base`，一个池子一个文件名即可独立成卡。

## 订阅

| 地址 | 内容 |
|---|---|
| `http://127.0.0.1:9098/api/sub` | base64 编码的 `ss://` 行（v2rayN / mihomo / sing-box 通用订阅格式） |
| `http://127.0.0.1:9098/api/ss` | 明文 `ss://` 行 |
| `http://127.0.0.1:9098/api/singbox` | sing-box outbound 片段 |

## 刷新

- 节点清单：`POST http://127.0.0.1:9098/api/refresh` 或 `python tools/harvest_fastvpn.py ./data`
- 探活：`python tools/probe_pool.py data/singbox_all_nodes.json data/probe_results.json`
- 稳定性：`python tools/stability.py data/nodes_live.json data/stability.json`

## 端口占用

| 用途 | 端口 |
|---|---|
| demo server | 9098 |
| 一次性测活/压测 | 22001–22006 / 23001–23006 |
| 常驻池 | 24001+ |

与 v2rayN 的 10808/10809 无交集。
