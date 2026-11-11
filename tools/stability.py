#!/usr/bin/env python3
"""稳定性采样: 每轮对所有节点并发打 HTTPS google 204, 统计成功率与 RTT 分布."""
import json, ssl, subprocess, sys, threading, time

sys.path.insert(0, '.')
from probe_pool import build_cfg
from bench_pool import socks_open

SB = r"C:\Users\Administrator.DESKTOP-EGNE9ND\Downloads\Compressed\v2rayN-windows-64-SelfContained\bin\sing_box\sing-box.exe"
CFG = r"C:\ev_tmp\pool_stab.json"
BASE = 22001
ROUNDS = 6

def tls_get(port, host, path, timeout=12):
    s = socks_open(port, host, 443, timeout)
    ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    ss = ctx.wrap_socket(s, server_hostname=host); ss.settimeout(timeout)
    ss.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
    t0 = time.time(); d = b""
    while True:
        c = ss.recv(8192)
        if not c: break
        d += c
        if len(d) > 4096: break
    ss.close()
    return int((time.time()-t0)*1000), d.split(b"\r\n")[0]

def main():
    nodes = json.load(open(sys.argv[1], encoding="utf-8"))
    live = [n for n in nodes if n.get("live")]
    open(CFG, "w", encoding="utf-8").write(json.dumps(build_cfg(live), ensure_ascii=False, indent=1))
    p = subprocess.Popen([SB, "run", "-c", CFG], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)
    stats = {n["tag"]: {"ok": 0, "rtts": [], "rounds": ROUNDS} for n in live}
    try:
        for r in range(ROUNDS):
            res = [None]*len(live)
            def w(i, n):
                try:
                    ms, head = tls_get(BASE+i, "www.google.com", "/generate_204")
                    res[i] = (ms, b"204" in head)
                except Exception:
                    res[i] = None
            ths = [threading.Thread(target=w, args=(i, n)) for i, n in enumerate(live)]
            for t in ths: t.start()
            for t in ths: t.join()
            for i, n in enumerate(live):
                if res[i] and res[i][1]:
                    stats[n["tag"]]["ok"] += 1
                    stats[n["tag"]]["rtts"].append(res[i][0])
            print(f"round {r+1}/{ROUNDS}: " + " ".join(
                f'{n["tag"].split()[0]}={"ok" if (res[i] and res[i][1]) else "x"}' for i, n in enumerate(live)), flush=True)
            time.sleep(1.5)
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()
    out = []
    for n in live:
        s = stats[n["tag"]]
        r = s["rtts"]
        out.append({"tag": n["tag"], "server": n["server"],
                    "success": f'{s["ok"]}/{s["rounds"]}',
                    "rate": round(s["ok"]/s["rounds"]*100),
                    "rtt_min": min(r) if r else None, "rtt_avg": round(sum(r)/len(r)) if r else None,
                    "rtt_max": max(r) if r else None})
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
