#!/usr/bin/env python3
"""极简 ELF64 动态符号解析 + A64 adr 常量提取（无 pyelftools 依赖）"""
import struct, sys, re

def load(path):
    return open(path,'rb').read()

def parse(path):
    b = load(path)
    assert b[:4] == b'\x7fELF' and b[4] == 2, "need ELF64"
    le = b[5] == 1
    e = '<' if le else '>'
    phoff = struct.unpack_from(e+'Q', b, 0x20)[0]
    phentsize = struct.unpack_from(e+'H', b, 0x36)[0]
    phnum = struct.unpack_from(e+'H', b, 0x38)[0]
    loads = []   # (vaddr, offset, filesz)
    dyn = None
    for i in range(phnum):
        o = phoff + i*phentsize
        p_type = struct.unpack_from(e+'I', b, o)[0]
        p_offset, p_vaddr, _, p_filesz = struct.unpack_from(e+'QQQQ', b, o+8)
        if p_type == 1:   # PT_LOAD
            loads.append((p_vaddr, p_offset, p_filesz))
        elif p_type == 2: # PT_DYNAMIC
            dyn = (p_offset, p_filesz)
    assert dyn, "no PT_DYNAMIC"
    d_off, d_sz = dyn
    tags = {}
    for o in range(d_off, d_off+d_sz, 16):
        tag, val = struct.unpack_from(e+'qQ', b, o)
        if tag == 0: break
        tags.setdefault(tag, val)
    symtab = tags[6]; strtab = tags[5]
    def v2o(addr):
        for vaddr, off, fsz in loads:
            if vaddr <= addr < vaddr+fsz:
                return off + (addr - vaddr)
        return None
    sym_off = v2o(symtab); str_off = v2o(strtab)
    # 符号数：用 strtab 后的第一个 sym 边界估计 — 直接扫到 strtab 起始
    nsym = (str_off - sym_off)//24 if str_off > sym_off else 0
    out = []
    for i in range(nsym):
        o = sym_off + i*24
        st_name = struct.unpack_from(e+'I', b, o)[0]
        st_value = struct.unpack_from(e+'Q', b, o+8)[0]
        st_size = struct.unpack_from(e+'Q', b, o+16)[0]
        if st_name == 0: continue
        end = b.index(b'\0', str_off+st_name)
        name = b[str_off+st_name:end].decode('utf-8','replace')
        if any(k in name for k in ('getAK','getEK','NativeBridge','VpnCoreProvider')):
            out.append((name, st_value, st_size))
    return b, v2o, out

if __name__ == '__main__':
    path = sys.argv[1]
    b, v2o, syms = parse(path)
    for name, val, sz in syms:
        print(f'{name}  vaddr=0x{val:x} size={sz} fileoff=0x{v2o(val):x}')
        off = v2o(val)
        code = b[off:off+min(sz or 64, 96)]
        words = struct.unpack_from('<%dI' % (len(code)//4), code, 0)
        print('  words:', ' '.join('%08x'%w for w in words[:16]))
