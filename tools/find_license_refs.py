"""定位 psdto3d101.exe 里引用授权字符串（.enc / USBKey / 格式串）的代码。"""
import struct
import sys

path = sys.argv[1] if len(sys.argv) > 1 else r'C:\Home\Workspace\UGit\psdto\Psdto3d\psdto3d101.exe'
d = open(path, 'rb').read()
e = struct.unpack_from('<I', d, 0x3c)[0]
nsec = struct.unpack_from('<H', d, e + 6)[0]
soh = struct.unpack_from('<H', d, e + 20)[0]
ib = struct.unpack_from('<I', d, e + 24 + 28)[0]
secs = []
s = e + 24 + soh
for i in range(nsec):
    b = s + 40 * i
    name = d[b:b + 8].rstrip(b'\0').decode('latin1')
    vs, va, rs, ro = struct.unpack_from('<IIII', d, b + 8)
    secs.append((name, va, vs, ro, rs))


def off2va(off):
    for name, va, vs, ro, rs in secs:
        if ro <= off < ro + rs:
            return va + (off - ro)
    return None


def va2off(va):
    for name, va0, vs, ro, rs in secs:
        if va0 <= va < va0 + max(vs, rs):
            return ro + (va - va0)
    return None


targets = {}
for pat in (b'.enc', b'MyUSBKey', b'USBKey', b'12345678', b'AuthTime', b'LKEY', b'HKEY'):
    start = 0
    while True:
        i = d.find(pat, start)
        if i < 0:
            break
        # 只取后面跟着 NUL 的独立字符串（Delphi 常量表里带长度头）
        if d[i + len(pat):i + len(pat) + 1] == b'\0' and i > 4:
            ln = struct.unpack_from('<I', d, i - 4)[0]
            if ln == len(pat):
                targets[i] = (pat.decode(), off2va(i))
        start = i + 1

print('字符串常量位置 (file_off -> VA):')
for off, (name, va) in sorted(targets.items()):
    print('  0x%06X -> VA 0x%08X  %r' % (off, va or 0, name))

# 在 CODE 里找 push imm32 引用
code_sec = [x for x in secs if x[0] == 'CODE'][0]
_, cva, cvs, cro, crs = code_sec
code = d[cro:cro + crs]
print('\nCODE 引用:')
for off, (name, va) in sorted(targets.items()):
    if va is None:
        continue
    pat = struct.pack('<I', ib + va)
    hits = []
    st = 0
    while True:
        i = code.find(pat, st)
        if i < 0:
            break
        hits.append(cva + i)
        st = i + 1
    if hits:
        print('  %-12r VA 0x%08X  被 %d 处引用: %s'
              % (name, va, len(hits), ', '.join('0x%08X' % h for h in hits[:10])))
