#!/usr/bin/env python3
"""极简 DEX 扫描器: 定位类 -> 方法 -> 方法体内引用的字符串常量.

不依赖 jadx/androguard, 只读 DEX 二进制结构.
用法: python dexscan.py <dexdir> <class-name-substring> [--strings]
"""
import struct, sys, os, glob

def uleb(b, o):
    r = 0; s = 0
    while True:
        x = b[o]; o += 1
        r |= (x & 0x7F) << s
        if not x & 0x80: return r, o
        s += 7

class Dex:
    def __init__(self, path):
        self.b = open(path, 'rb').read()
        b = self.b
        self.soff, self.ssz = struct.unpack_from('<II', b, 0x3C)[0], struct.unpack_from('<I', b, 0x38)[0]
        self.moff, self.msz = struct.unpack_from('<II', b, 0x5C)[0], struct.unpack_from('<I', b, 0x58)[0]
        self.coff, self.csz = struct.unpack_from('<I', b, 0x64)[0], struct.unpack_from('<I', b, 0x60)[0]
        self._str = {}
        self._mth = {}

    def string(self, idx):
        if idx in self._str: return self._str[idx]
        off = struct.unpack_from('<I', self.b, self.soff + idx * 4)[0]
        _, off = uleb(self.b, off)
        end = self.b.index(b'\0', off)
        s = self.b[off:end].decode('utf-8', 'replace')
        self._str[idx] = s
        return s

    def method(self, idx):
        if idx in self._mth: return self._mth[idx]
        o = self.moff + idx * 8
        cidx, _, nidx = struct.unpack_from('<HHI', self.b, o)
        cls = self.string(cidx)
        name = self.string(nidx)
        self._mth[idx] = (cls, name)
        return self._mth[idx]

    def classes(self):
        for i in range(self.csz):
            o = self.coff + i * 32
            cidx, _, _, _, _, _, data_off, _ = struct.unpack_from('<IIIIIIII', self.b, o)
            yield self.string(cidx), data_off

    def methods_of(self, data_off):
        b = self.b; o = data_off
        sf, o = uleb(b, o); inf, o = uleb(b, o)
        dm, o = uleb(b, o); vm, o = uleb(b, o)
        for _ in range(sf + inf):
            _, o = uleb(b, o); _, o = uleb(b, o)
        out = []
        for count in (dm, vm):
            last = 0
            for _ in range(count):
                diff, o = uleb(b, o); _, o = uleb(b, o); code_off, o = uleb(b, o)
                last += diff
                out.append((last, code_off))
        return out

    def const_strings(self, code_off):
        if not code_off: return []
        b = self.b
        insns_size = struct.unpack_from('<I', b, code_off + 12)[0]
        base = code_off + 16
        res = []
        i = 0
        while i < insns_size:
            w = struct.unpack_from('<H', b, base + i * 2)[0]
            op = w & 0xFF
            if op == 0x1A and i + 1 < insns_size:
                sidx = struct.unpack_from('<H', b, base + (i + 1) * 2)[0]
                if sidx < self.ssz:
                    res.append(self.string(sidx))
                i += 2; continue
            if op == 0x1B and i + 2 < insns_size:
                sidx = struct.unpack_from('<I', b, base + (i + 1) * 2)[0]
                if sidx < self.ssz:
                    res.append(self.string(sidx))
                i += 3; continue
            i += 1
        return res

def scan(dexdir, needle, show_strings=True):
    for f in sorted(glob.glob(os.path.join(dexdir, 'classes*.dex'))):
        d = Dex(f)
        for cname, data_off in d.classes():
            if needle.lower() not in cname.lower(): continue
            print(f'\n### {cname}   [{os.path.basename(f)}]')
            if not data_off: continue
            for midx, code_off in d.methods_of(data_off):
                _, mname = d.method(midx)
                consts = d.const_strings(code_off)
                if show_strings and consts:
                    print(f'  {mname}:')
                    for s in consts[:40]:
                        print(f'      {s!r}')
                else:
                    print(f'  {mname}')

if __name__ == '__main__':
    scan(sys.argv[1], sys.argv[2], '--no-strings' not in sys.argv)
