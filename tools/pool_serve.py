#!/usr/bin/env python3
"""常驻代理池: 每个节点一个本地 socks5 端口, 周期测活, 输出 proxies.txt.

不设置系统代理, 仅监听 127.0.0.1:24xxx.
用法: python tools/pool_serve.py [--interval 300]
"""
import json, os, socket, struct, subprocess, sys, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SINGBOX = r"C:\Users\Administrator.DESKTOP-EGNE9ND\Downloads\Compressed\v2rayN-windows-64-SelfContained\bin\sing_box\sing-box.exe"
CFG = r"C:\ev_tmp\pool_serve.json"
PORT_FILE = os.path.join(ROOT, "data", "proxies.txt")
PORT_MAP = os.path.join(ROOT, "data", "port_map.json")
BASE_PORT = 24001

def build(nodes):
    inb, outb, rules = [], [], []
    for i, n in enumerate(nodes):
        ti, to = f"in{i}", f"out{i}"
        inb.append({"type": "socks", "tag": ti, "listen": "127.0.0.1", "listen_port": BASE_PORT + i})
        ob = {"type": "shadowsocks", "tag": to, "server": n["server"], "server_port": n["server_port"],
              "method": n["method"], "password": n["password"]}
        if n.get("plugin"):
            ob["plugin"] = n["plugin"]; ob["plugin_opts"] = n["plugin_opts"]
        outb.append(ob); rules.append({"inbound": [ti], "outbound": to})
    return {"log": {"level": "warn"}, "inbounds": inb,
            "outbounds": outb + [{"type": "direct", "tag": "direct"}],
            "route": {"rules": rules, "final": "direct"}}

def alive(port, timeout=8):
    try:
        t0 = time.time()
        s = socket.create_connection(("127.0.0.1", port), timeout); s.settimeout(timeout)
        s.sendall(b"\x05\x01\x00")
        if s.recv(2) != b"\x05\x00": return None
        h = b"www.gstatic.com"
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(h)]) + h + struct.pack("!H", 80))
        r = s.recv(4)
        if len(r) < 4 or r[1] != 0: return None
        at = r[3]
        if at == 1: s.recv(4)
        elif at == 3: s.recv(s.recv(1)[0])
        elif at == 4: s.recv(16)
        s.recv(2)
        s.sendall(b"GET /generate_204 HTTP/1.1\r\nHost: www.gstatic.com\r\nConnection: close\r\n\r\n")
        d = s.recv(64); s.close()
        return int((time.time()-t0)*1000) if b"204" in d else None
    except Exception:
        return None

def main():
    interval = 300
    if "--interval" in sys.argv:
        interval = int(sys.argv[sys.argv.index("--interval")+1])
    nodes = json.load(open(os.path.join(ROOT, "data", "stable_nodes.json"), encoding="utf-8"))
    nodes = [n for n in nodes if n.get("live")]
    open(CFG, "w", encoding="utf-8").write(json.dumps(build(nodes), ensure_ascii=False, indent=1))
    proc = subprocess.Popen([SINGBOX, "run", "-c", CFG], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)
    if proc.poll() is not None:
        print("sing-box 启动失败"); return
    print(f"pool up: {len(nodes)} nodes, {BASE_PORT}..{BASE_PORT+len(nodes)-1}, interval={interval}s")
    try:
        while True:
            ok, pmap = [], {}
            for i, n in enumerate(nodes):
                port = BASE_PORT + i
                rtt = alive(port)
                pmap[n["tag"]] = {"port": port, "rtt": rtt,
                                  "server": n["server"], "proto": n["type"]}
                if rtt:
                    ok.append(f"socks5://127.0.0.1:{port}")
            with open(PORT_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(ok) + "\n")
            json.dump(pmap, open(PORT_MAP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"[{time.strftime('%H:%M:%S')}] alive {len(ok)}/{len(nodes)} -> {PORT_FILE}")
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except Exception: proc.kill()

if __name__ == "__main__":
    main()
