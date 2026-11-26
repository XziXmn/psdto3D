# -*- coding: utf-8 -*-
"""实验：把 PSD 每层的 alpha 通道去掉（只保留 RGB），看是否触发"background layer"报错。

    python tools/strip_alpha.py in.psd out.psd
"""
import struct
import sys


def parse(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'8BPS'
    h, w = struct.unpack('>II', d[14:22])
    depth, mode = struct.unpack('>HH', d[22:26])
    chans = struct.unpack('>H', d[12:14])[0]
    p = 26
    n = struct.unpack('>I', d[p:p + 4])[0]; p += 4
    cm = d[p:p + n]; p += n
    n = struct.unpack('>I', d[p:p + 4])[0]; p += 4
    ir = d[p:p + n]; p += n
    lm_len = struct.unpack('>I', d[p:p + 4])[0]; p += 4
    lm_end = p + lm_len
    p += 4                                  # layer info length
    cnt = abs(struct.unpack('>h', d[p:p + 2])[0]); p += 2

    layers = []
    for _ in range(cnt):
        start = p
        p += 16
        nch = struct.unpack('>H', d[p:p + 2])[0]; p += 2
        chans_info = []
        for _c in range(nch):
            cid, ln = struct.unpack('>hI', d[p:p + 6]); p += 6
            chans_info.append((cid, ln))
        p += 12
        ex = struct.unpack('>I', d[p:p + 4])[0]; p += 4
        p += ex
        layers.append({'rect': start, 'chans': chans_info, 'rec': d[start:p]})

    for lay in layers:
        total = sum(ln for _, ln in lay['chans'])
        lay['data'] = d[p:p + total]
        p += total

    merged = d[lm_end:]
    return dict(w=w, h=h, depth=depth, mode=mode, chans=chans, cm=cm, ir=ir,
                layers=layers, merged=merged)


def build(info, path, keep_alpha=False):
    recs = bytearray()
    data = bytearray()
    for lay in info['layers']:
        cinfo = lay['chans']
        blocks = []
        off = 0
        for cid, ln in cinfo:
            blocks.append((cid, lay['data'][off:off + ln]))
            off += ln
        if not keep_alpha:
            blocks = [b for b in blocks if b[0] != -1]
        rec = bytearray(16)
        rec += struct.pack('>H', len(blocks))
        for cid, blk in blocks:
            rec += struct.pack('>hI', cid, len(blk))
        # 复用原记录的尾部（blend/extra）
        tail_off = 16 + 2 + len(cinfo) * 6
        rest = lay['rec'][tail_off:]
        rec += rest
        recs += rec
        for _, blk in blocks:
            data += blk

    li = struct.pack('>h', len(info['layers'])) + bytes(recs) + bytes(data)
    lm = struct.pack('>I', len(li)) + li + struct.pack('>I', 0)
    out = bytearray()
    out += b'8BPS' + struct.pack('>H', 1) + b'\x00' * 6
    out += struct.pack('>HIIHH', info['chans'], info['h'], info['w'], info['depth'], info['mode'])
    out += struct.pack('>I', len(info['cm'])) + info['cm']
    out += struct.pack('>I', len(info['ir'])) + info['ir']
    out += struct.pack('>I', len(lm)) + lm
    out += info['merged']
    open(path, 'wb').write(bytes(out))
    print('写出 %s（%d 层，%s alpha）' % (path, len(info['layers']), '保留' if keep_alpha else '去掉'))


if __name__ == '__main__':
    info = parse(sys.argv[1])
    build(info, sys.argv[2], keep_alpha=False)
