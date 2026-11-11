#!/usr/bin/env python3
"""节点池压测: 延迟采样 + 单流带宽 + 6 并发成功率. 全程走本地隔离 socks, 不碰系统代理."""
import json, os, socket, struct, subprocess, sys, threading, time

SINGBOX = r"C:\Users\Administrator.DESKTOP-EGNE9ND\Downloads\Compressed\v2rayN-windows-64-SelfContained\bin\sing_box\sing-box.exe"
BASE_PORT = 23001
CFG = r"C:\ev_tmp\pool_bench.json"
SPEED_HOST = "speedtest.ams1.nl.leaseweb.net"
SPEED_PATH = "/10mb.bin"
SPEED_BYTES = 5_000_000

def build_cfg(nodes):
    inb, outb, rules = [], [], []
    for i, n in enumerate(nodes):
        ti, to = f"in{i}", f"out{i}"
        inb.append({"type": "socks", "tag": ti, "listen": "127.0.0.1", "listen_port": BASE_PORT + i})
        ob = {"type": "shadowsocks", "tag": to, "server": n["server"], "server_port": n["server_port"],
              "method": n["method"], "password": n["password"]}
        if n.get("plugin"):
            ob["plugin"] = n["plugin"]; ob["plugin_opts"] = n["plugin_opts"]
        outb.append(ob); rules.append({"inbound": [ti], "outbound": to})
    return {"log": {"level": "warn", "timestamp": False}, "inbounds": inb,
            "outbounds": outb + [{"type": "direct", "tag": "direct"}],
            "route": {"rules": rules, "final": "direct"}}

def socks_open(port, host, dport, timeout):
    s = socket.create_connection(("127.0.0.1", port), timeout); s.settimeout(timeout)
    s.sendall(b"\x05\x01\x00")
    if s.recv(2) != b"\x05\x00": raise IOError("auth")
    hb = host.encode()
    s.sendall(b"\x05\x01\x00\x03" + bytes([len(hb)]) + hb + struct.pack("!H", dport))
    r = s.recv(4)
    if len(r) < 4 or r[1] != 0: raise IOError("rep")
    at = r[3]
    if at == 1: s.recv(4)
    elif at == 3: s.recv(s.recv(1)[0])
    elif at == 4: s.recv(16)
    s.recv(2)
    return s

def http_req(port, host, path, timeout=15):
    s = socks_open(port, host, 80, timeout)
    s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
    t0 = time.time(); total = 0
    head = b""
    first = None
    while True:
        c = s.recv(65536)
        if not c: break
        if first is None: first = time.time() - t0
        head += c; total += len(c)
        if head.find(b"\r\n\r\n") >= 0 and total > SPEED_BYTES + 4096: break
    s.close()
    return time.time() - t0, first, total

def latency(port, rounds=5):
    ok, rtts = 0, []
    for _ in range(rounds):
        try:
            t0 = time.time()
            s = socks_open(port, "www.gstatic.com", 80, 8)
            s.sendall(b"GET /generate_204 HTTP/1.1\r\nHost: www.gstatic.com\r\nConnection: close\r\n\r\n")
            d = s.recv(64); s.close()
            if b"204" in d: ok += 1; rtts.append(int((time.time()-t0)*1000))
        except Exception:
            pass
    return ok, rtts

def speed(port, tries=2):
    best = 0
    for _ in range(tries):
        try:
            el, first, n = http_req(port, SPEED_HOST, SPEED_PATH, timeout=40)
            mbps = (n * 8) / el / 1e6
            best = max(best, mbps)
        except Exception:
            pass
    return round(best, 2)

def burst(port, conc=6):
    res = [None]*conc
    def w(i):
        try:
            s = socks_open(port, "www.gstatic.com", 80, 10)
            s.sendall(b"GET /generate_204 HTTP/1.1\r\nHost: www.gstatic.com\r\nConnection: close\r\n\r\n")
            d = s.recv(64); s.close()
            res[i] = b"204" in d
        except Exception:
            res[i] = False
    ths = [threading.Thread(target=w, args=(i,)) for i in range(conc)]
    t0 = time.time()
    for t in ths: t.start()
    for t in ths: t.join()
    return sum(1 for x in res if x), int((time.time()-t0)*1000)

def main():
    nodes = json.load(open(sys.argv[1], encoding="utf-8"))
    live = [n for n in nodes if n.get("live")]
    open(CFG, "w", encoding="utf-8").write(json.dumps(build_cfg(live), ensure_ascii=False, indent=1))
    proc = subprocess.Popen([SINGBOX, "run", "-c", CFG], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(2.5)
    if proc.poll() is not None:
        print("sing-box 起不来:", proc.stderr.read().decode("utf-8", "replace")[:600]); return
    out = []
    try:
        for i, n in enumerate(live):
            p = BASE_PORT + i
            ok, rtts = latency(p)
            sp = speed(p) if ok else 0
            bs, bc = burst(p) if ok else (0, 0)
            rec = {"tag": n["tag"], "server": n["server"], "lat_ok": f"{ok}/5",
                   "rtt_min": min(rtts) if rtts else None, "rtt_max": max(rtts) if rtts else None,
                   "mbps": sp, "burst": f"{bs}/6", "burst_ms": bc}
            out.append(rec)
            print(flush=True) or print(f'{n["tag"]:<20} lat {ok}/5  rtt {rec["rtt_min"]}-{rec["rtt_max"]}ms  {sp} Mbps  burst {rec["burst"]}')
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except Exception: proc.kill()
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
