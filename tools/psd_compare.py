# -*- coding: utf-8 -*-
"""Compare two PSD files structurally (header / layer records / names / channel heads).

    python tools/psd_compare.py ours.psd ref.psd
"""
import struct
import sys


def parse(path):
    with open(path, 'rb') as fh:
        head = fh.read(26)
        sig, ver = head[:4], struct.unpack('>H', head[4:6])[0]
        ch, h, w, depth, mode = struct.unpack('>HIIHH', head[12:26])
        def u32():
            return struct.unpack('>I', fh.read(4))[0]
        cm = u32()
        fh.seek(cm, 1)                   # 颜色模式数据
        ir = u32()
        fh.seek(ir, 1)                   # 图像资源
        lm_len = u32()
        li_len = u32()
        n = abs(struct.unpack('>h', fh.read(2))[0])
        layers = []
        for i in range(n):
            top, left, bottom, right = struct.unpack('>iiii', fh.read(16))
            nch = struct.unpack('>H', fh.read(2))[0]
            chans = []
            for _ in range(nch):
                cid, ln = struct.unpack('>hI', fh.read(6))
                chans.append((cid, ln))
            blend = fh.read(8)
            fh.read(4)                   # opacity/clip/flags/filler
            extra_len = u32()
            extra = fh.read(extra_len)
            name = ''
            if extra_len >= 8:
                mask_len = struct.unpack('>I', extra[0:4])[0]
                p = 4 + mask_len
                if p + 4 <= len(extra):
                    blend_len = struct.unpack('>I', extra[p:p + 4])[0]
                    p += 4 + blend_len
                    if p < len(extra):
                        ln = extra[p]
                        name = extra[p + 1:p + 1 + ln].decode('latin1')
            layers.append({'rect': (top, left, bottom, right), 'chans': chans,
                           'name': name, 'extra_len': extra_len})
        return {'sig': sig, 'ver': ver, 'ch': ch, 'h': h, 'w': w, 'depth': depth,
                'mode': mode, 'lm_len': lm_len, 'li_len': li_len, 'layers': layers,
                'pos_after_records': fh.tell()}


def main():
    a_path, b_path = sys.argv[1], sys.argv[2]
    a, b = parse(a_path), parse(b_path)
    print('%-8s %-28s %s' % ('', 'ours', 'ref'))
    for k in ('sig', 'ver', 'ch', 'h', 'w', 'depth', 'mode'):
        same = '✅' if a[k] == b[k] else '❌'
        print('%-8s %-28s %-28s %s' % (k, a[k], b[k], same))
    print('layers   %-28d %-28d %s' % (len(a['layers']), len(b['layers']),
                                       '✅' if len(a['layers']) == len(b['layers']) else '❌'))
    print('li_len   %-28d %-28d' % (a['li_len'], b['li_len']))
    print()
    print('%3s %-26s %-26s %-8s %-8s %s' % ('#', 'ours rect', 'ref rect', 'our name', 'ref name', 'chans'))
    for i, (la, lb) in enumerate(zip(a['layers'], b['layers']), 1):
        ok = '✅' if la['rect'] == lb['rect'] and la['chans'] == lb['chans'] else '❌'
        print('%3d %-26s %-26s %-8s %-8s %s' % (i, la['rect'], lb['rect'], la['name'],
                                                lb['name'], ok))
        if i >= 3:
            break
    print('...（其余层结构相同则上面 ✅）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
