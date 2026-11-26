"""把 PSDTO3D 写 TIFF 头用的 Delphi 字符串常量改回正确值（对标 99 版）。

背景
----
`ok3d4.dll` / `cmyktiff2.dll` 代码段里有一组 Delphi `string` 常量，结构是

    ff ff ff ff | len:dword | chars | 0 填充（4 字节对齐）

它们决定写出的 TIFF 头字段：

    位序  2022 里的坏值   99 版里的好值   含义
    0     18261          18761          0x4949 = 'II'，TIFF 魔数
    1     423            42             TIFF 版本号
    2     1              8              IFD 偏移
    3     259            256            0x0100 ImageWidth
    4     19             16             条目数
    5     274            273            0x0111 StripOffsets

没有硬件狗时用的是坏值，写出来的文件前 8 字节是 `55 47 a7 01 01 00 00 00`
（"UG"），任何标准阅读器都拒绝打开。99 版（厂商无狗分支）里两套都在，用的是好值。

每个槽位都恰好同长（16/12/12/12/12/12 字节），所以是纯等长替换。

用法：
    python tools/patch_tiff_consts.py <dll> [-o out.dll]
"""
import argparse
import sys

FIXES = [
    (b'18261', b'18761'),
    (b'423',   b'42'),
    (b'1',     b'8'),
    (b'259',   b'256'),
    (b'274',   b'273'),
]
REFCNT = b'\xff\xff\xff\xff'


def struct_bytes(val):
    pad = (-len(val)) % 4
    return REFCNT + len(val).to_bytes(4, 'little') + val + b'\x00' * pad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dll')
    ap.add_argument('-o', '--output', default=None)
    a = ap.parse_args()

    d = bytearray(open(a.dll, 'rb').read())
    print('%s  (%d 字节)' % (a.dll, len(d)))
    cursor = 0                      # 表内顺序固定，顺序扫描即可唯一定位
    for old, new in FIXES:
        ob, nb = struct_bytes(old), struct_bytes(new)
        if len(ob) != len(nb):
            raise SystemExit('槽位不等长，拒绝改写: %r -> %r' % (old, new))
        off = d.find(ob, cursor)
        if off < 0:
            raise SystemExit('找不到常量结构 %r（从 0x%X 起）' % (old, cursor))
        d[off:off + len(ob)] = nb
        cursor = off + len(ob)
        print('  %-6r -> %-6r  @0x%06X  (%d 字节槽位)' % (old, new, off, len(ob)))
    out = a.output or a.dll
    open(out, 'wb').write(bytes(d))
    print('已写出 %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
