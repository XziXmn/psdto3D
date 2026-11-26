# -*- coding: utf-8 -*-
"""实验：把某个图层改名成 "</Layer group>"（组结束标记），看是否触发 background 报错。"""
import struct
import sys


def parse(path):
    d = open(path, 'rb').read()
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
    p += 4
    cnt = abs(struct.unpack('>h', d[p:p + 2])[0]); p += 2
    layers = []
    for _ in range(cnt):
        start = p
        p += 16
        nch = struct.unpack('>H', d[p:p + 2])[0]; p += 2
        ci = []
        for _c in range(nch):
            cid, ln = struct.unpack('>hI', d[p:p + 6]); p += 6
            ci.append((cid, ln))
        p += 12
        ex = struct.unpack('>I', d[p:p + 4])[0]; p += 4
        ex_start = p
        p += ex
        layers.append({'rec': d[start:p], 'ex_start': ex_start - start, 'ex_len': ex, 'ci': ci})
    for lay in layers:
        total = sum(ln for _, ln in lay['ci'])
        lay['data'] = d[p:p + total]
        p += total
    return dict(w=w, h=h, depth=depth, mode=mode, chans=chans, cm=cm, ir=ir, layers=layers,
                merged=d[lm_end:])


def rename_first(info, path, newname):
    lay = info['layers'][0]
    rec = bytearray(lay['rec'])
    ex0 = lay['ex_start']
    ex = rec[ex0:ex0 + lay['ex_len']]
    mask_len = struct.unpack('>I', ex[0:4])[0]
    q = 4 + mask_len
    blend_len = struct.unpack('>I', ex[q:q + 4])[0]
    q += 4
    name_pos = q
    old_len = ex[name_pos]
    body = bytearray(ex[:name_pos]) 
    nm = newname.encode('latin1')
    pstr = bytes([len(nm)]) + nm
    while len(pstr) % 4:
        pstr += b'\x00'
    body += pstr
    body += ex[name_pos + 1 + old_len:]
    # 重新拼记录
    head = rec[:ex0 - 4]
    newrec = bytes(head) + struct.pack('>I', len(body)) + bytes(body)
    recs = bytearray()
    data = bytearray()
    for i, l in enumerate(info['layers']):
        recs += newrec if i == 0 else l['rec']
        data += l['data']
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
    print('写出 %s：第 1 层改名为 %r' % (path, newname))


if __name__ == '__main__':
    info = parse(sys.argv[1])
    rename_first(info, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '</Layer group>')
