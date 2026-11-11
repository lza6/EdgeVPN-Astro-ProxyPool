# EdgeVPN (com.edgevpn.secure.proxy.unblock) 1.7.9 Mod 逆向报告

日期：2026-11-11 ｜ 样本：`com.edgevpn.secure.proxy.unblock_v1.7.9_Mod.apk`（29.6 MB）

## 1. 画像

| 项 | 值 |
|---|---|
| 包名 | `com.edgevpn.secure.proxy.unblock`（dex 内部包名仍为 `com.example.newvpn`） |
| 版本 / 渠道 | 1.7.9，Mod（签名 `META-INF/TRUMODS.RSA`） |
| 厂商工程 | `E:/AndroidStudioProjects/VPN_Waqas/app/src/main/cpp/vpnModule.cpp` |
| 家族 | astroapps / Alestrasol 白标（同 `com.fast.vpn.secure.unblock.proxy` 2.1.5） |
| 隧道内核 | `libopenvpn.so`（ics-openvpn）、`libsslocal.so`（shadowsocks-android）、`libtun2socks.so`、`libredsocks.so` |
| 自有 native | `libunblock.so` 62 KB、`libnative-lib.so` 46 KB（仅密钥 JNI） |
| UI | Jetpack Compose + androidx.navigation + Hilt + WorkManager |
| 计费 | RevenueCat（`api-production.8-lives-cat.io` / `rev.cat`） |
| 广告 | AdMob、Meta Audience Network、Mintegral、Vungle、Yandex |
| 推送 | Firebase `edge-vpn-3a844` |

APK 里 5 个业务 dex（classes.dex 10.2 MB / classes3 7.6 / classes4 7.1 / classes5 4.3 / classes2+6 小）合计 34 990 类。原始样本的时间戳语义（classes2/3/4 为 1981-01-01）表明 classes.dex、classes5、classes6 是 Mod 打包时重新生成的。

## 2. 代码保护状态（重要）

`com.example.newvpn.*` 的类名保留，但**类体被替换**：`utils/ApiService` 的方法体是 `androidx.navigation` 的代码，`viewmodel/ServersViewModel`（classes.dex）只有 `a`/`b` 两个空方法，同名类在 classes3.dex 里则是 `LocationResult` 的实现。`method_ids` 的 `class_idx` 指向字符串常量而非类型描述符。

结论：**dex 层做了类重打包 / 成员错位**，jadx 1.5.1 三种模式（auto、fallback、single-class）均无法产出可读代码（加载 34 990 类后在 code cache 阶段失败）。静态可读的只剩：

- 字符串池（`https://edgeapi.astroapps.io/api/`、`https://countryflags.astroapps.io/`、`support@edgevpn.app`）
- native 段（符号表、.rodata、A64 立即数/常量池）
- `resources.arsc`（`Refresh servers from subscription`、`edge-vpn-3a844.firebasestorage.app` 等）

## 3. native 密钥链（全部静态还原）

### 3.1 libunblock.so

ELF64，`DT_SYMTAB` 10 个符号，无 GNU_HASH 依赖可直接遍历。两个 JNI 导出：

```
Java_com_example_newvpn_hilt_VpnCoreProvider_getAK        @0x708  (152 B)
Java_com_example_newvpn_hilt_VpnCoreProvider_getEKPartA   @0x7a0  (20 B)
```

`getAK` 用 `MOVZ`/`MOVK` 立即数在栈上拼 8 字节：

```
0x720 d28c29c9  movz  x9, #0x614e, lsl #0
0x72c f2ad2e89  movk  x9, #0x6974, lsl #16
0x734 f2ccaec9  movk  x9, #0x6576, lsl #32
0x73c f2eca969  movk  x9, #0x654b, lsl #48
=> 小端字节 4e 61 74 69 76 65 4b 65  =  "NativeKe"
```

`getEKPartA` 是 20 字节桩：

```
0x7a0 f9400008  ldr  x8, [x0]
0x7a8 10ffed01  adr  x1, 0x548      ; immhi=0x7ff68 immlo=0 -> imm=-0x260, pc=0x7a8
0x7b0 d61f0040  br   x2             ; JNIEnv->NewStringUTF
```

`0x548` 处即字符串 `eiNrMJ5W/Mng/67VnLbqHqrFnzO0ylDwnwJcvSjUuIwF`（44 字符，标准 base64，解 33 字节）。

### 3.2 libnative-lib.so（遗留通道，与 FastVPN 相同）

```
Java_com_alestrasol_vpn_di_NativeBridge_getAK   @0x740   NEON 常量池 -> 3c1256a97e1139bc1d42584f61121317
Java_com_alestrasol_vpn_di_NativeBridge_getEK   @0x7d4   adr x1, 0x550 -> tpPEcc4XmUavOyKkwDfc5cmA+...Zgg=
```

`getEK` 返回值与 FastVPN 2.1.5 样本**逐字节相同**，`nativeKeyHalf` 字段名也一致。

## 4. 节点下发

### 4.1 两个域名

```
App 写入      https://edgeapi.astroapps.io/api/      (dex 字符串, classes.dex #40429)
国家旗帜      https://countryflags.astroapps.io/<cc>.png
同族端点      https://avapi.astroapps.io/api/getNewServers   (FastVPN 2.1.5 用)
```

三者 DNS 全部指向同一 Cloudflare 集群（104.26.6.186 / 104.26.7.186 / 172.67.73.138）。

本机实测：

| 域名 | 直连 | 经节点 |
|---|---|---|
| `edgeapi.astroapps.io` | TLS 握手即 `ECONNRESET`（SNI 阻断），3/3 复现 | 可达，Node/Express |
| `avapi.astroapps.io` | TLS 1.3 正常 | 可达 |

`edgeapi` 的 Express 对 `/api/getNewServers`、`/api/getServers`、`/api/getAllServers`、`/api/servers`、`/api/v2/servers`、`/api/config`、`/api/newServers` 全部返回 `Cannot GET <path>`。**该域名是另一套 Node 后端，路径未还原**（dex 混淆阻断静态定位，盲探无收敛）。

### 4.2 同族端点可用

```
GET https://avapi.astroapps.io/api/getNewServers
header: key: poi_xYCJzovnpEKX4CEWPrHSLme2pMfmGe3lP1AA
-> 200, {"code":200,"data":[...46 条...]}
```

GCM key 构造沿用 FastVPN：

```
AK = 3c1256a97e1139bc1d42584f61121317        (16B)
key = AK ‖ 79134290 ‖ a11f3e7a ‖ c05da329 ‖ 61771920   (32B)
AES-256-GCM, IV = 密文前 12B, tag = 末 16B
```

节点字段解密（AES-256-CBC，key `47DEQpj8HBSa+/TImW+5JCeuQeRkm5NM` / iv `x3VmCsrqXavLbbps`）46/46 成功。纯 IP 字段为明文；16 B 短密文无 PKCS5，按尾字节剥自定义 pad。

## 5. 池构成（2026-11-11 快照）

| 协议 | 数量 | 端口 | 加密 | 实测 |
|---|---|---|---|---|
| shadowsocks | 9 | 443 | chacha20-ietf-poly1305 | 一级 6/9；6 轮稳定性采样中 2 台 100%、1 台 67%、3 台 ≤33% |
| v2ray（实为 SS + v2ray-plugin ws/tls） | 3 | 443 | 同上 | TLS 一级未通，需 sing-box plugin 侧验证 |
| openvpn | 34 | UDP 1194-1197 | tls-crypt，证书内嵌，无 auth-user-pass | TCP 探测无意义，待实连 |

free 24 / premium 22，字段结构一致，服务端未按付费态分流。

节点 IP 集中在 ColoCrossing 系：`108.181.x`、`67.220.x`、`134.195.x`、`136.176.x`、`38.99.x`、`208.69.x`。

## 6. 出口验证

SS 节点为 NAT 池出口，**入口 IP ≠ 出口 IP**，同 AS 同网段：

| 城市 | 入口 | 实测出口 |
|---|---|---|
| Ashburn II | 108.181.133.138 | 108.181.133.97 |
| Montreal II | 134.195.198.163 | 134.195.198.212 |
| Los Angeles II | 108.181.9.202 | 108.181.0.177 |
| Amsterdam II | 108.181.122.170 | 108.181.58.239 |

判定口径：`exit_ip` 必须由 `ip-api.com` 在隧道内返回，且与入口同 ASN 段；仅 `curl` 退出码不作数。

稳定性（6 轮、每轮 6 节点并发打 `https://www.google.com/generate_204`）：

| 节点 | 成功率 | RTT avg |
|---|---|---|
| Los Angeles II | 100% | 198 ms |
| Montreal II | 100% | 646 ms |
| Barcelona II | 67% | 3557 ms |
| Dallas II | 33% | 4788 ms |
| Ashburn II | 17% | 2718 ms |
| Amsterdam II | 0% | — |

带宽无法测：出口对 `speed.cloudflare.com`、`speedtest.ams1.nl.leaseweb.net`、`speedtest.tele2.net`、`ipv4.download.thinkbroadband.com` 的 443 握手一律超时，`/10mb.bin` 类资源不可达。判定节点质量改用 HTTPS 204 成功率 + RTT 分布。

## 7. 未解与阻塞

1. `edgeapi.astroapps.io` 路由表：dex 类体错位导致路径常量无法定位；App 侧需要动态（模拟器 + frida）才能拿到真实请求路径。本机无 Android SDK / AVD，未执行。
2. `getAK()="NativeKe"` 与 `getEKPartA` 的 Java 侧拼接逻辑未还原（同上原因）。当前 API key 来自 libnative-lib 遗留通道。
3. 3 台 v2ray-plugin 与 34 台 OpenVPN 未做二级实测。

## 8. 合规

节点为第三方商业资源。研究 / 自用 / 内部演练范围内使用；对外售卖或大规模转售属未授权使用。
