#!/usr/bin/env python3
"""提取 DEX 中的注解 (尤其 Retrofit @GET/@POST/@Headers/@Header)."""
import struct, sys, glob

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
        self.soff = struct.unpack_from('<I', b, 0x3C)[0]; self.ssz = struct.unpack_from('<I', b, 0x38)[0]
        self.moff = struct.unpack_from('<I', b, 0x5C)[0]; self.msz = struct.unpack_from('<I', b, 0x58)[0]
        self.coff = struct.unpack_from('<I', b, 0x64)[0]; self.csz = struct.unpack_from('<I', b, 0x60)[0]
        self._c = {}

    def string(self, idx):
        if idx in self._c: return self._c[idx]
        off = struct.unpack_from('<I', self.b, self.soff + idx*4)[0]
        _, off = uleb(self.b, off)
        end = self.b.index(b'\0', off)
        s = self.b[off:end].decode('utf-8', 'replace'); self._c[idx] = s
        return s

    def classes(self):
        for i in range(self.csz):
            o = self.coff + i*32
            v = struct.unpack_from('<IIIIIIII', self.b, o)
            yield v[0], v[6], v[5], v[1]   # class_idx, data_off, annotations_off, access

    def val(self, o):
        b = self.b
        head = b[o]; o += 1
        vt = head & 0x1F; arg = head >> 5
        if vt == 0x17 or vt == 0x18 or vt == 0x1A or vt == 0x19 or vt == 0x1B:
            idx, o = uleb(b, o)
            return ('str' if vt == 0x17 else 'ref', self.string(idx)), o
        if vt == 0x1C:
            n, o = uleb(b, o)
            arr = []
            for _ in range(n):
                v, o = self.val(o); arr.append(v)
            return ('arr', arr), o
        if vt == 0x1D:
            return self.ann(o)
        if vt == 0x1E: return ('null', None), o
        if vt == 0x1F: return ('bool', bool(arg)), o
        size = arg + 1
        raw = b[o:o+size]; o += size
        return ('num', int.from_bytes(raw, 'little', signed=(vt in (0,2,3,4,6)))), o

    def ann(self, o):
        b = self.b
        tidx, o = uleb(b, o)
        n, o = uleb(b, o)
        els = {}
        for _ in range(n):
            nidx, o = uleb(b, o)
            v, o = self.val(o)
            els[self.string(nidx)] = v
        return ('ann', self.string(tidx), els), o

    def read_set(self, off):
        b = self.b
        if not off: return []
        n = struct.unpack_from('<I', b, off)[0]; o = off+4; out=[]
        for _ in range(n):
            aoff = struct.unpack_from('<I', b, o)[0]; o += 4
            vis = b[aoff]
            try:
                _, v = self.ann(aoff+1)
                out.append(v)
            except Exception:
                pass
        return out

def scan(dexdir, filt=None):
    for f in sorted(glob.glob(dexdir + '/classes*.dex')):
        d = Dex(f)
        for cidx, doff, aoff, access in d.classes():
            cname = d.string(cidx)
            if not aoff: continue
            b = d.b
            dir_off = aoff
            cls_ann = struct.unpack_from('<I', b, dir_off)[0]
            nf, nm, np_ = struct.unpack_from('<III', b, dir_off+4)
            hits = []
            if cls_ann:
                hits.append(('CLASS', d.read_set(cls_ann)))
            o = dir_off + 16
            for j in range(nf):
                fidx = struct.unpack_from('<I', b, o)[0]; soff = struct.unpack_from('<I', b, o+4)[0]; o += 8
                hits.append(('FIELD', d.read_set(soff)))
            for j in range(nm):
                midx = struct.unpack_from('<I', b, o)[0]; soff = struct.unpack_from('<I', b, o+4)[0]; o += 8
                mo = d.moff + midx*8
                nn = d.string(struct.unpack_from('<HHI', b, mo)[2])
                hits.append(('METHOD ' + nn, d.read_set(soff)))
            txt = str(hits)
            if 'retrofit2/http' not in txt: continue
            if filt and filt.lower() not in cname.lower(): continue
            print(f'\n### {cname}  [{f.split(chr(92))[-1]}]')
            for tag, anns in hits:
                for a in anns:
                    if isinstance(a, tuple) and a[0] == 'ann' and 'retrofit2/http' in a[1]:
                        print('   ', tag, a[1], a[2])

if __name__ == '__main__':
    scan(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
