#!/usr/bin/env python3
"""通过本地 socks 节点访问目标 (HTTPS), 用于确认 edgeapi 真实路径."""
import socket, ssl, struct, sys, time

def socks_open(port, host, dport, timeout=15):
    s = socket.create_connection(("127.0.0.1", port), timeout); s.settimeout(timeout)
    s.sendall(b"\x05\x01\x00")
    if s.recv(2) != b"\x05\x00": raise IOError("socks auth")
    hb = host.encode()
    s.sendall(b"\x05\x01\x00\x03" + bytes([len(hb)]) + hb + struct.pack("!H", dport))
    r = s.recv(4)
    if len(r) < 4 or r[1] != 0: raise IOError("rep=%d" % (r[1] if len(r) > 1 else -1))
    at = r[3]
    if at == 1: s.recv(4)
    elif at == 3: s.recv(s.recv(1)[0])
    elif at == 4: s.recv(16)
    s.recv(2)
    return s

def fetch(port, url_host, path, key=None, timeout=15):
    raw = socks_open(port, url_host, 443, timeout)
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    ss = ctx.wrap_socket(raw, server_hostname=url_host)
    hdr = f"GET {path} HTTP/1.1\r\nHost: {url_host}\r\nUser-Agent: okhttp/4.12.0\r\nAccept: application/json\r\nConnection: close\r\n"
    if key: hdr += f"key: {key}\r\n"
    ss.sendall((hdr + "\r\n").encode())
    data = b""
    while True:
        c = ss.recv(8192)
        if not c: break
        data += c
    ss.close()
    i = data.find(b"\r\n\r\n")
    head, body = data[:i], data[i+4:]
    return head.split(b"\r\n")[0].decode("utf-8", "replace"), body

if __name__ == "__main__":
    port = int(sys.argv[1]); host = sys.argv[2]; key = sys.argv[3] if len(sys.argv) > 3 else None
    paths = sys.argv[4:] or ["/", "/api/", "/api/getNewServers"]
    for p in paths:
        try:
            st, body = fetch(port, host, p, key)
            print(f"{p:<28} {st}  {body[:220]!r}")
        except Exception as e:
            print(f"{p:<28} ERR {type(e).__name__}: {str(e)[:100]}")
