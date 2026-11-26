# -*- coding: utf-8 -*-
"""把一个真实 PSD 的图层复制到指定数量，生成"结构完全合法"的 N 层 PSD（用于测试层数上限）。

    python tools/clone_psd_layers.py in.psd out.psd --layers 50
"""
import argparse
import struct
import sys


def parse(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'8BPS'
    h, w = struct.unpack('>II', d[14:22])
    depth, mode = struct.unpack('>HH', d[22:26])
    chans = struct.unpack('>H', d[12:14])[0]
    p = 26
    cm_len = struct.unpack('>I', d[p:p + 4])[0]; p += 4
    cm = d[p:p + cm_len]; p += cm_len
    ir_len = struct.unpack('>I', d[p:p + 4])[0]; p += 4
    ir = d[p:p + ir_len]; p += ir_len
    lm_len = struct.unpack('>I', d[p:p + 4])[0]; p += 4
    lm_end = p + lm_len
    li_len = struct.unpack('>I', d[p:p + 4])[0]; p += 4
    li_end = p + li_len
    n = abs(struct.unpack('>h', d[p:p + 2])[0]); p += 2

    layers = []
    for _ in range(n):
        start = p
        p += 16
        nch = struct.unpack('>H', d[p:p + 2])[0]; p += 2
        chans_info = []
        for _c in range(nch):
            cid, ln = struct.unpack('>hI', d[p:p + 6]); p += 6
            chans_info.append((cid, ln))
        p += 12                                   # blend + opacity/clip/flags/filler
        ex_len = struct.unpack('>I', d[p:p + 4])[0]; p += 4
        p += ex_len
        layers.append({'record': d[start:p], 'chans': chans_info})

    # 通道数据
    for lay in layers:
        off = p
        for cid, ln in lay['chans']:
            pass
        lay['data_start'] = p
        total = 0
        for cid, ln in lay['chans']:
            total += 2 + ln if False else ln          # ln 已含 2 字节压缩标志
        lay['data'] = d[p:p + sum(ln for _, ln in lay['chans'])]
        p += len(lay['data'])

    merged = d[lm_end:]
    return {'w': w, 'h': h, 'depth': depth, 'mode': mode, 'chans': chans,
            'cm': cm, 'ir': ir, 'layers': layers, 'merged': merged}


def build(src, dst, count):
    info = parse(src)
    layers = info['layers']
    if not layers:
        raise SystemExit('源文件没有图层')
    seq = [layers[i % len(layers)] for i in range(count)]

    recs = b''.join(l['record'] for l in seq)
    data = b''.join(l['data'] for l in seq)
    li = struct.pack('>h', count) + recs + data
    lm = struct.pack('>I', len(li)) + li + struct.pack('>I', 0)

    out = bytearray()
    out += b'8BPS' + struct.pack('>H', 1) + b'\x00' * 6
    out += struct.pack('>HIIHH', info['chans'], info['h'], info['w'], info['depth'], info['mode'])
    out += struct.pack('>I', len(info['cm'])) + info['cm']
    out += struct.pack('>I', len(info['ir'])) + info['ir']
    out += struct.pack('>I', len(lm)) + lm
    out += info['merged']
    open(dst, 'wb').write(bytes(out))
    print('写出 %s：%d 层（源 %d 层）%dx%d，%d 字节'
          % (dst, count, len(layers), info['w'], info['h'], len(out)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--layers', type=int, default=50)
    a = ap.parse_args()
    build(a.src, a.dst, a.layers)


if __name__ == '__main__':
    main()
