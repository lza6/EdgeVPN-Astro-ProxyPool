#!/usr/bin/env python3
"""EdgeVPN / astroapps 节点池 demo server (127.0.0.1:9098).

端点:
  GET  /             状态页
  GET  /api/servers  46 节点全量 (解密后)
  GET  /api/live     经实测存活的节点 (含延迟/带宽)
  GET  /api/singbox  sing-box outbound 片段
  GET  /api/ss       ss:// 分享链接
  GET  /api/sub      标准 base64 订阅 (v2rayN/mihomo 可直接导入)
  GET  /api/proxies  socks 池格式 / 节点清单
  POST /api/refresh  重新收割上游
不设置任何系统代理, 不影响本机 v2ray。
"""
import base64, json, os, sys, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "tools"))
PORT = 9098

def load(name, default=None):
    p = os.path.join(ROOT, "data", name)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8", errors="replace"))
    return default

def ss_links(nodes):
    out = []
    for n in nodes:
        if n.get("type") != "ss" or n.get("plugin"):
            continue
        ui = base64.urlsafe_b64encode(f'{n["method"]}:{n["password"]}'.encode()).decode().rstrip("=")
        out.append(f'ss://{ui}@{n["server"]}:{n["server_port"]}#{urllib.parse.quote(n["tag"])}')
    return out

def render_index():
    nodes = load("servers_decrypted.json", [])
    probe = {x["tag"]: x for x in load("probe_results.json", [])}
    bench = {x["tag"]: x for x in load("bench_results.json", [])}
    stab = {x["tag"]: x for x in load("stability.json", [])}
    proto = {}
    for n in nodes:
        proto[n.get("protocol")] = proto.get(n.get("protocol"), 0) + 1
    rows = []
    for n in nodes:
        tag = n.get("city_name", "")
        st = stab.get(tag, {}); p = probe.get(tag, {})
        if st.get("success"):
            state = f'{st["success"]} · {st.get("rtt_avg") or "-"}ms'
        elif p.get("gstatic"):
            state = f'1/1 · {p.get("rtt_ms","-")}ms'
        elif p:
            state = "dead"
        else:
            state = "-"
        rows.append(
            f'<tr><td>{tag}</td><td>{n.get("country_name","")}</td><td>{n.get("protocol")}</td>'
            f'<td>{n.get("type")}</td><td>{n.get("ipaddress") or n.get("domain")}</td>'
            f'<td>{n.get("port")}</td><td>{state}</td></tr>')
    stats = "".join(f'<span class="stat">{k}: {v}</span>' for k, v in proto.items())
    live_n = sum(1 for v in probe.values() if v.get("gstatic"))
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>EdgeVPN 节点池</title>
<style>body{{font-family:system-ui;background:#0b1220;color:#e2e8f0;margin:0;padding:24px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid #1e293b;padding:6px 10px;text-align:left}}
th{{background:#16213a;color:#93c5fd}}h1{{font-size:19px;margin:0 0 4px}}
.stat{{display:inline-block;background:#16213a;padding:6px 14px;border-radius:8px;margin:0 8px 8px 0;font-size:13px}}
a{{color:#7dd3fc}}.muted{{color:#64748b;font-size:12px}}</style></head>
<body><h1>EdgeVPN (astroapps) 节点池</h1>
<p class="muted">源 API: avapi.astroapps.io/api/getNewServers · 密钥链 native getAK/getEKPartA · 实测走本地隔离 socks</p>
<p><span class="stat">总计 {len(nodes)}</span>{stats}<span class="stat">实测存活 {live_n}</span></p>
<p><a href="/api/servers">servers</a> · <a href="/api/live">live</a> · <a href="/api/singbox">singbox</a>
 · <a href="/api/ss">ss</a> · <a href="/api/sub">订阅</a> · <a href="/api/proxies">proxies</a></p>
<table><tr><th>城市</th><th>国家</th><th>协议</th><th>类型</th><th>地址</th><th>端口</th><th>稳定性 · RTT</th></tr>
{''.join(rows)}</table></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            self._send(200, render_index(), "text/html; charset=utf-8")
        elif u.path == "/api/servers":
            self._send(200, json.dumps(load("servers_decrypted.json", []), ensure_ascii=False, indent=1))
        elif u.path == "/api/live":
            probe = load("probe_results.json", [])
            bench = {x["tag"]: x for x in load("bench_results.json", [])}
            out = [x for x in probe if x.get("gstatic")]
            for x in out:
                if x["tag"] in bench:
                    x.update({"bench": bench[x["tag"]]})
            self._send(200, json.dumps(out, ensure_ascii=False, indent=1))
        elif u.path == "/api/singbox":
            self._send(200, json.dumps(load("singbox_all_nodes.json", []), ensure_ascii=False, indent=1))
        elif u.path == "/api/ss":
            self._send(200, "\n".join(ss_links(load("singbox_all_nodes.json", []))), "text/plain; charset=utf-8")
        elif u.path == "/api/sub":
            body = "\n".join(ss_links(load("singbox_all_nodes.json", [])))
            self._send(200, base64.b64encode(body.encode()).decode(), "text/plain; charset=utf-8")
        elif u.path == "/api/proxies":
            lines = ["# EdgeVPN/astroapps 节点清单 (城市 | 协议 | 地址:端口)"]
            for n in load("servers_decrypted.json", []):
                host = n.get("ipaddress") or n.get("domain")
                lines.append(f'{n.get("city_name")} | {n.get("protocol")} | {host}:{n.get("port")}')
            self._send(200, "\n".join(lines), "text/plain; charset=utf-8")
        else:
            self._send(404, '{"error":"not found"}')

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path == "/api/refresh":
            try:
                from harvest_fastvpn import decrypt_all, fetch_servers
                servers = decrypt_all(fetch_servers())
                json.dump(servers, open(os.path.join(ROOT, "data", "servers_decrypted.json"), "w",
                                        encoding="utf-8"), ensure_ascii=False, indent=1)
                self._send(200, json.dumps({"ok": True, "servers": len(servers)}))
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "err": str(e)[:200]}))
        else:
            self._send(404, '{"error":"not found"}')

if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"demo -> http://127.0.0.1:{PORT}/")
    srv.serve_forever()
