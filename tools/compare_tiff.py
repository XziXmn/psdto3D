"""看 / 比 PSDTO3D 写出的 TIFF 头（支持它那个非标准的 "UG" 变体）。

    python tools/compare_tiff.py a.tif                # 单个文件：打表
    python tools/compare_tiff.py a.tif b.tif          # 两个文件：逐字段对比

它会把头解析成 IFD 条目表，并把 tag 翻译成名字，直接指出哪些字段是坏的。
"""
import struct
import sys

NAMES = {
    0x0100: 'ImageWidth', 0x0101: 'ImageLength', 0x0102: 'BitsPerSample',
    0x0103: 'Compression', 0x0106: 'Photometric', 0x010E: 'ImageDescription',
    0x0111: 'StripOffsets', 0x0112: 'Orientation', 0x0115: 'SamplesPerPixel',
    0x0116: 'RowsPerStrip', 0x0117: 'StripByteCounts', 0x011A: 'XResolution',
    0x011B: 'YResolution', 0x011C: 'PlanarConfig', 0x0128: 'ResolutionUnit',
    0x0131: 'Software', 0x0132: 'DateTime', 0x013B: 'Artist',
}
TYPES = {1: ('BYTE', 1), 2: ('ASCII', 1), 3: ('SHORT', 2), 4: ('LONG', 4),
         5: ('RATIONAL', 8)}


def parse(path):
    d = open(path, 'rb').read()
    info = {'path': path, 'size': len(d), 'head16': d[:16].hex(' ')}
    if d[:2] == b'II':
        fmt, ifd = '<', struct.unpack('<I', d[4:8])[0]
        info['flavor'] = 'II (标准小端)'
    elif d[:2] == b'MM':
        fmt, ifd = '>', struct.unpack('>I', d[4:8])[0]
        info['flavor'] = 'MM (标准大端)'
    else:
        # 厂商的坏变体：8 字节前导 + IFD 在 8
        fmt, ifd = '<', 8
        info['flavor'] = '非标准前导 %r -> IFD 假定在 8' % d[:2]
    info['fmt'], info['ifd'] = fmt, ifd
    n = struct.unpack(fmt + 'H', d[ifd:ifd + 2])[0]
    info['count'] = n
    entries = []
    p = ifd + 2
    for i in range(n):
        if p + 12 > len(d):
            break
        tag, typ, cnt = struct.unpack(fmt + 'HHI', d[p:p + 8])
        raw = d[p + 8:p + 12]
        (tname, tsize) = TYPES.get(typ, ('?%d' % typ, 1))
        if tsize * cnt <= 4:
            v = struct.unpack(fmt + 'H', raw[:2])[0] if typ == 3 else raw[0] \
                if typ in (1, 2) else struct.unpack(fmt + 'I', raw)[0]
        else:
            v = ' -> 0x%X' % struct.unpack(fmt + 'I', raw)[0]
        entries.append({'i': i, 'off': p, 'tag': tag, 'type': tnam if False else tname,
                        'typ': typ, 'count': cnt, 'value': v, 'raw': raw})
        p += 12
    info['entries'] = entries
    info['next_ifd_at'] = p
    info['next_ifd'] = struct.unpack(fmt + 'I', d[p:p + 4])[0] if p + 4 <= len(d) else None
    return info


def show(info):
    print('=' * 74)
    print(info['path'])
    print('  大小 %d   %s' % (info['size'], info['flavor']))
    print('  前 16 字节: %s' % info['head16'])
    print('  IFD @ %d, 条目数 %d, 后继 IFD = %s'
          % (info['ifd'], info['count'], info['next_ifd']))
    print('  %-3s %-6s %-12s %-9s %-5s %s' % ('#', 'tag', 'name', 'type', 'cnt', 'value'))
    for e in info['entries']:
        name = NAMES.get(e['tag'], '?')
        print('  %-3d 0x%04X %-12s %-9s %-5d %s'
              % (e['i'], e['tag'], name, e['type'], e['count'], e['value']))
    print()


def required(info):
    """标准 TIFF 必须有这些 tag，返回缺失/异常清单。"""
    have = {e['tag']: e for e in info['entries']}
    problems = []
    for tag, need in [(0x0100, 'ImageWidth'), (0x0101, 'ImageLength'),
                      (0x0102, 'BitsPerSample'), (0x0103, 'Compression'),
                      (0x0106, 'Photometric'), (0x0111, 'StripOffsets'),
                      (0x0115, 'SamplesPerPixel'), (0x0116, 'RowsPerStrip'),
                      (0x0117, 'StripByteCounts')]:
        if tag not in have:
            problems.append('缺 0x%04X %s' % (tag, need))
    extra = [e for e in info['entries']
             if e['tag'] not in NAMES and e['tag'] < 0xC000]
    for e in extra:
        problems.append('多余/非法 tag 0x%04X (值 %s)' % (e['tag'], e['value']))
    return problems


def compare(a, b):
    print('=' * 74)
    print('对比: %s\n   vs %s' % (a['path'], b['path']))
    print('  前 16 字节: %s' % ('一致' if a['head16'] == b['head16']
                                else '\n    A %s\n    B %s' % (a['head16'], b['head16'])))
    print('  条目数: A=%d  B=%d  %s'
          % (a['count'], b['count'], '一致' if a['count'] == b['count'] else '**不同**'))
    ta = [(e['tag'], e['value']) for e in a['entries']]
    tb = [(e['tag'], e['value']) for e in b['entries']]
    if ta == tb:
        print('  条目表完全一致')
    else:
        print('  条目表不同：')
        for i in range(max(len(ta), len(tb))):
            x = ta[i] if i < len(ta) else None
            y = tb[i] if i < len(tb) else None
            if x != y:
                fx = ('0x%04X = %s' % x) if x else '(无)'
                fy = ('0x%04X = %s' % y) if y else '(无)'
                print('    #%-2d A: %-22s  B: %-22s' % (i, fx, fy))
    print()


def main():
    files = sys.argv[1:]
    if not files:
        print(__doc__)
        return 1
    infos = [parse(f) for f in files]
    for i in infos:
        show(i)
        probs = required(i)
        if probs:
            print('  这个头不合规：')
            for p in probs:
                print('    · %s' % p)
        else:
            print('  头看起来是标准 TIFF ✔')
        print()
    if len(infos) == 2:
        compare(*infos)
    return 0


if __name__ == '__main__':
    sys.exit(main())
