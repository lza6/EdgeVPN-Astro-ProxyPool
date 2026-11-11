# EdgeVPN-ProxyPool

来源：`com.edgevpn.secure.proxy.unblock_v1.7.9_Mod.apk`（Mod 签名 TRUMODS，内部包名仍为 `com.example.newvpn`，开发者工程目录 `E:/AndroidStudioProjects/VPN_Waqas`）。

astroapps / Alestrasol 白标 VPN 家族成员，与 `com.fast.vpn.secure.unblock.proxy`（FastVPN 2.1.5）同后端、同密钥链。本仓库交付其节点池、实测结论与可直接接入的池产物。

## 状态

| 模块 | 状态 | 依据 |
|---|---|---|
| APK 结构画像 | 已验证 | unzip 清单 + AndroidManifest |
| native 密钥链 | 已验证 | ELF dynsym 定位 + A64 MOVZ/MOVK 与 adr 手工解码 |
| 节点下发 API | 已验证 | `GET https://avapi.astroapps.io/api/getNewServers`，header `key`，200 / 46 节点 |
| 字段解密 | 已验证 | AES-256-CBC（key/iv 同 FastVPN），46 条全解，0 报错 |
| 节点协议识别 | 已验证 | 9 shadowsocks / 3 "v2ray"(SS+v2ray-plugin) / 34 openvpn |
| 代理级真活 | 已验证 | 本地隔离 sing-box，socks5 握手 + gstatic 204 + 出口 IP：6/9 SS 通 |
| 压测（延迟/带宽/并发） | 部分验证 | `data/bench_results.json`；出口对测速站有拦截，带宽未取得有效样本 |
| 稳定性采样 | 已验证 | `data/stability.json`，6 轮 HTTPS 204：2 台 100%，1 台 67%，3 台 ≤33% |
| OpenVPN 实连 | 待验证 | 34 份配置 UDP，需 OpenVPN 客户端实连 |
| demo server | 已验证 | 127.0.0.1:9098，6 端点全 200 |
| 常驻池服务 | 已验证 | `tools/pool_serve.py`，每节点一 socks 端口 + 周期测活 |

## 关键事实

```
包名          com.edgevpn.secure.proxy.unblock   (内部 com.example.newvpn)
版本          1.7.9 Mod
内核          libopenvpn.so / libsslocal.so / libtun2socks.so / libredsocks.so / libunblock.so
UI            Jetpack Compose + androidx.navigation + Hilt
计费          RevenueCat (api-production.8-lives-cat.io)
广告          AdMob / Meta / Mintegral / Vungle / Yandex
Firebase      edge-vpn-3a844
App 自带 base https://edgeapi.astroapps.io/api/     ← 本机直连被 RST，需经节点访问
同族可用 API  https://avapi.astroapps.io/api/getNewServers   ← 200，返回本池节点
```

## native 密钥链

```
[1] libunblock.so  Java_com_example_newvpn_hilt_VpnCoreProvider_getAK
      0x720 movz x9,#0x614e ; movk 0x6974 lsl16 ; movk 0x6576 lsl32 ; movk 0x654b lsl48
      -> 8 字节 "NativeKe"
    Java_com_example_newvpn_hilt_VpnCoreProvider_getEKPartA
      0x7a8 adr x1, 0x548  -> "eiNrMJ5W/Mng/67VnLbqHqrFnzO0ylDwnwJcvSjUuIwF"

[2] libnative-lib.so  Java_com_alestrasol_vpn_di_NativeBridge_getAK / getEK
      getAK -> 16B NEON 常量 3c1256a97e1139bc1d42584f61121317
      getEK -> tpPEcc4XmUavOyKkwDfc5cmA+nxFimNi7E/a94lYd8QH/eOxwS0KWz1OJPYbmdaDJkJwAL4Z6KmM4m/abD5QUXyzZgg=
      （与 FastVPN 2.1.5 逐字节相同）

[3] GCM key = AK ‖ 79134290 ‖ a11f3e7a ‖ c05da329 ‖ 61771920  (32B)
    AES-256-GCM, IV=密文前 12B, tag=末 16B
    -> API key: poi_xYCJzovnpEKX4CEWPrHSLme2pMfmGe3lP1AA

[4] 节点字段 AES-256-CBC
    key 47DEQpj8HBSa+/TImW+5JCeuQeRkm5NM
    iv  x3VmCsrqXavLbbps
    纯 IP 明文直通；16B 短密文按尾字节剥自定义 pad
```

## 数据产物

| 文件 | 内容 |
|---|---|
| `data/servers_decrypted.json` | 46 节点全字段（明文 IP/密码/加密方式） |
| `data/singbox_all_nodes.json` | sing-box outbound 片段（12 条 SS 系） |
| `data/ss_links.txt` | 9 条 `ss://` 分享链接 |
| `data/probe_results.json` | 一级/二级测活（延迟 + 出口 IP + 204） |
| `data/bench_results.json` | 压测（5 次延迟采样 / 5MB 单流带宽 / 6 并发） |
| `data/nodes_live.json` | 带 `live` 标记的一级测活通过集（6 台） |
| `data/stability.json` | 6 轮稳定性采样（成功率 / RTT 分布） |
| `data/stable_nodes.json` | 入池子集（2 台，100% 成功） |
| `data/proxies.txt` | 常驻池输出（`socks5://127.0.0.1:24xxx`，new-api 可直接吃） |
| `data/port_map.json` | 端口 ↔ 城市/节点映射 |

## 实测矩阵（6 轮 HTTPS google/generate_204，并发采样）

| 节点 | 成功率 | RTT min / avg / max | 入池 |
|---|---|---|---|
| Los Angeles II | 6/6 (100%) | 186 / 198 / 206 ms | ✅ |
| Montreal II | 6/6 (100%) | 256 / 646 / 1551 ms | ✅ |
| Barcelona II | 4/6 (67%) | 1407 / 3557 / 7354 ms | 慢，剔除 |
| Dallas II | 2/6 (33%) | 3707 / 4788 / 5870 ms | ✗ |
| Ashburn II | 1/6 (17%) | 2718 ms | ✗ |
| Amsterdam II | 0/6 | — | ✗ |

`data/stable_nodes.json` = 成功率 ≥60% 且 avg RTT <3 s 的子集（2 台）。

带宽：出口对 `speed.cloudflare.com` / `leaseweb` / `tele2` / `thinkbroadband` 的 443 握手全部超时，5 MB 拉取无有效样本。可用性判定改用 HTTPS 204，比 ICMP / 裸 TCP 更接近真实业务。

## 用法

```bash
# 收割（重跑上游，覆盖 data/servers_decrypted.json）
python tools/harvest_fastvpn.py ./data

# 测活（隔离 sing-box，端口 22001+）
python tools/probe_pool.py data/singbox_all_nodes.json data/probe_results.json

# 压测（隔离 sing-box，端口 23001+）
python tools/bench_pool.py data/nodes_live.json data/bench_results.json

# demo（127.0.0.1:9098）
python demo_server.py

# 常驻池（127.0.0.1:24001+，每 5 分钟刷新 data/proxies.txt）
python tools/pool_serve.py --interval 300
```

本机 v2rayN 占用 `10808`。以上全部走独立端口 + 独立 sing-box 实例，不改任何系统代理、环境变量或 DNS。

## 订阅

`http://127.0.0.1:9098/api/sub` 为标准 base64 订阅（v2rayN / mihomo / sing-box 通用，内容为 `ss://` 行）。

## 限制

- `edgeapi.astroapps.io` 是本 App 自己写入的 base URL，本机直连 TLS 即被 RST；经节点访问返回 Express 404（`Cannot GET /api/getNewServers`），说明该域名跑的是另一套 Node 后端、路径尚未还原。当前池来自同族 `avapi` 端点。
- 3 台 "v2ray" 节点为 SS + v2ray-plugin（ws+tls），需 sing-box 侧 plugin 支持；本次一级 TLS 握手未通。
- 34 台 OpenVPN 为 UDP + tls-crypt，证书内嵌、无 `auth-user-pass`，TCP 探测无意义，需实连判定。
- 节点为第三方商业资源，仅研究/自用；对外转售属未授权使用。
