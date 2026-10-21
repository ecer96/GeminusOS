#!/usr/bin/env python3
"""Reconstruye el resource (RSCE) del FIT de arranque con los logos nuevos
y actualiza todos los hashes (RSCE sha1 por entrada + FIT sha256 del resource).
"""
import struct, hashlib

SRC = 'bootp_backup.bin'
OUT = 'bootp_geminus.bin'
RES_OFF = 0x25D1200
RES_SIZE = 0x25AC00
FIT_HDR = 0x600
NTAB = 0x1800


def align(x, a=512):
    return (x + a - 1) // a * a


src = bytearray(open(SRC, 'rb').read())
assert src[:4] == b'\xd0\x0d\xfe\xed', 'no es un FIT'

# ---------- 1. reconstruir RSCE ----------
res = bytes(src[RES_OFF:RES_OFF + RES_SIZE])
assert res[:4] == b'RSCE'

ents = []
for i in range(1, NTAB // 0x200):
    e = res[i * 0x200:(i + 1) * 0x200]
    name = e.split(b'\x00')[0]
    if not name:
        continue
    off, size = struct.unpack('<II', e[0x104:0x10C])
    data = res[off * 512:off * 512 + size]
    assert hashlib.sha1(data).digest() == e[0xE0:0xE0 + 20], f'sha1 original malo en {name}'
    ents.append([i, name, bytearray(e), data])

repl = {
    b'ENTRlogo.bmp': open('uboot_new.bmp', 'rb').read(),
    b'ENTRlogo_kernel.bmp': open('kernel_new.bmp', 'rb').read(),
}

table = bytearray(res[:NTAB])
ptr = NTAB
for i, name, e, data in ents:
    if name in repl:
        data = repl[name]
    size = len(data)
    struct.pack_into('<I', e, 0x104, ptr // 512)
    struct.pack_into('<I', e, 0x108, size)
    struct.pack_into('<I', e, 0x100, 20)
    e[0xE0:0xE0 + 20] = hashlib.sha1(data).digest()
    table[i * 0x200:(i + 1) * 0x200] = e
    if len(table) < ptr + size:
        table.extend(b'\x00' * (ptr + size - len(table)))
    table[ptr:ptr + size] = data
    print(f'  {name.decode():22s} off=0x{ptr:<8x} size={size:<9d} sha1={hashlib.sha1(data).hexdigest()[:16]}')
    ptr = align(ptr + size)

newres = bytes(table[:ptr])
print(f'resource: {RES_SIZE} -> {len(newres)} bytes')

# ---------- 2. localizar propiedades del FIT ----------
off_struct = struct.unpack('>I', src[8:12])[0]
off_strings = struct.unpack('>I', src[12:16])[0]

found = {}
path = []
p = off_struct
while True:
    tok = struct.unpack('>I', src[p:p + 4])[0]; p += 4
    if tok == 1:  # BEGIN_NODE
        end = src.index(b'\x00', p)
        name = src[p:end].decode()
        p = (end + 4) & ~3
        path.append(name)
    elif tok == 3:  # PROP
        ln, nameoff = struct.unpack('>II', src[p:p + 8]); p += 8
        e = src.index(b'\x00', off_strings + nameoff)
        pname = src[off_strings + nameoff:e].decode()
        cur = '/' + '/'.join([x for x in path if x])
        found[(cur, pname)] = (p, ln)
        p = (p + ln + 3) & ~3
    elif tok == 2:
        path.pop()
    elif tok == 9:
        break

print('propiedades:', {k: (hex(v[0]), v[1]) for k, v in found.items() if k[1] in ('totalsize', 'data-size', 'value')})

tot_off = found[('/', 'totalsize')][0]
datasz_off = found[('/images/resource', 'data-size')][0]
hash_off = found[('/images/resource/hash', 'value')][0]

new_total = RES_OFF + len(newres) + FIT_HDR
struct.pack_into('>I', src, tot_off, new_total)
struct.pack_into('>I', src, datasz_off, len(newres))
new_hash = hashlib.sha256(newres).digest()
src[hash_off:hash_off + 32] = new_hash
print(f'totalsize: 0x{new_total:x}  data-size: 0x{len(newres):x}  sha256: {new_hash.hex()}')

# ---------- 3. escribir imagen ----------
src = bytearray(src)
if len(src) < RES_OFF + len(newres):
    src.extend(b'\x00' * (RES_OFF + len(newres) - len(src)))
src[RES_OFF:RES_OFF + len(newres)] = newres
# limpiar resto del area antigua si sobra
if len(newres) < RES_SIZE:
    src[RES_OFF + len(newres):RES_OFF + RES_SIZE] = b'\x00' * (RES_SIZE - len(newres))

open(OUT, 'wb').write(src)
print(f'escrito {OUT} ({len(src)} bytes, md5 pendiente)')
