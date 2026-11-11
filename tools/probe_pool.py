#!/usr/bin/env python3
"""astroapps / EdgeVPN 节点池测活: 每节点一个本地 socks 入站, 独立进程, 不碰系统代理."""
import json, os, socket, struct, subprocess, sys, time

SINGBOX = r"C:\Users\Administrator.DESKTOP-EGNE9ND\Downloads\Compressed\v2rayN-windows-64-SelfContained\bin\sing_box\sing-box.exe"
BASE_PORT = 22001
CFG = r"C:\ev_tmp\pool_probe.json"

def build_cfg(nodes):
    inb, outb, rules = [], [], []
    for i, n in enumerate(nodes):
        tag_in, tag_out = f"in{i}", f"out{i}"
        inb.append({"type": "socks", "tag": tag_in, "listen": "127.0.0.1", "listen_port": BASE_PORT + i})
        if n["type"] == "ss":
            ob = {"type": "shadowsocks", "tag": tag_out, "server": n["server"],
                  "server_port": n["server_port"], "method": n["method"], "password": n["password"]}
        else:
            ob = {"type": "shadowsocks", "tag": tag_out, "server": n["server"],
                  "server_port": n["server_port"], "method": n["method"], "password": n["password"]}
            if n.get("plugin"):
                ob["plugin"] = n["plugin"]; ob["plugin_opts"] = n["plugin_opts"]
        outb.append(ob)
        rules.append({"inbound": [tag_in], "outbound": tag_out})
    return {"log": {"level": "warn", "timestamp": False}, "inbounds": inb,
            "outbounds": outb + [{"type": "direct", "tag": "direct"}],
            "route": {"rules": rules, "final": "direct"}}

def socks5_http(port, host, dport, req, timeout=10):
    s = socket.create_connection(("127.0.0.1", port), timeout)
    s.settimeout(timeout)
    s.sendall(b"\x05\x01\x00")
    if s.recv(2) != b"\x05\x00": raise IOError("socks auth")
    hb = host.encode()
    s.sendall(b"\x05\x01\x00\x03" + bytes([len(hb)]) + hb + struct.pack("!H", dport))
    r = s.recv(4)
    if len(r) < 4 or r[1] != 0: raise IOError("socks connect rep=%d" % (r[1] if len(r) > 1 else -1))
    atyp = r[3]
    if atyp == 1: s.recv(4)
    elif atyp == 3: s.recv(s.recv(1)[0])
    elif atyp == 4: s.recv(16)
    s.recv(2)
    s.sendall(req)
    data = b""
    while True:
        c = s.recv(4096)
        if not c: break
        data += c
    s.close()
    return data

def body_of(raw):
    i = raw.find(b"\r\n\r\n")
    return raw[i+4:] if i >= 0 else raw

def probe_one(port, timeout=10):
    res = {}
    t0 = time.time()
    try:
        raw = socks5_http(port, "www.gstatic.com", 80,
                          b"GET /generate_204 HTTP/1.1\r\nHost: www.gstatic.com\r\nConnection: close\r\n\r\n", timeout)
        res["rtt_ms"] = int((time.time() - t0) * 1000)
        res["gstatic"] = b"204" in raw.split(b"\r\n")[0]
    except Exception as e:
        res["rtt_ms"] = None; res["gstatic"] = False; res["err"] = str(e)[:60]
        return res
    try:
        raw = socks5_http(port, "ip-api.com", 80,
                          b"GET /json/?fields=status,country,city,isp,as,query HTTP/1.1\r\nHost: ip-api.com\r\nConnection: close\r\n\r\n", timeout)
        res["ipinfo"] = json.loads(body_of(raw).decode("utf-8", "replace"))
    except Exception as e:
        res["ipinfo"] = {"err": str(e)[:60]}
    return res

def main():
    nodes = json.load(open(sys.argv[1], encoding="utf-8"))
    cfg = build_cfg(nodes)
    open(CFG, "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=1))
    proc = subprocess.Popen([SINGBOX, "run", "-c", CFG], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(2.5)
    if proc.poll() is not None:
        print("sing-box 启动失败:", proc.stderr.read().decode("utf-8", "replace")[:800]); return
    out = []
    try:
        for i, n in enumerate(nodes):
            r = probe_one(BASE_PORT + i)
            r2 = {"tag": n["tag"], "server": n["server"], "port": n["server_port"],
                  "proto": n["type"], **r}
            out.append(r2)
            ip = (r.get("ipinfo") or {}).get("query", "-")
            print(f'{n["tag"]:<22} {n["server"]:<16} {str(r.get("rtt_ms")):>6}ms  exit={ip}  g204={r.get("gstatic")}')
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except Exception: proc.kill()
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
