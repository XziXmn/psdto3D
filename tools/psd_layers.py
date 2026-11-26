# -*- coding: utf-8 -*-
"""列出 PSD 每层的关键信息：名字、通道、是否带蒙版/附加信息块（lsct 等）。"""
import struct
import sys


def dump(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'8BPS'
    h, w = struct.unpack('>II', d[14:22])
    chans = struct.unpack('>H', d[12:14])[0]
    mode = struct.unpack('>H', d[24:26])[0]
    p = 26
    n = struct.unpack('>I', d[p:p + 4])[0]; p += 4 + n
    n = struct.unpack('>I', d[p:p + 4])[0]; p += 4 + n
    p += 4
    p += 4
    raw = struct.unpack('>h', d[p:p + 2])[0]; p += 2
    cnt = abs(raw)
    print('尺寸 %dx%d 通道 %d 模式 %d 层数 %d（原始计数字段 %d）' % (w, h, chans, mode, cnt, raw))
    for i in range(cnt):
        rect = struct.unpack('>iiii', d[p:p + 16]); p += 16
        nch = struct.unpack('>H', d[p:p + 2])[0]; p += 2
        ids = []
        for _ in range(nch):
            cid, ln = struct.unpack('>hI', d[p:p + 6]); p += 6
            ids.append(cid)
        p += 12
        ex = struct.unpack('>I', d[p:p + 4])[0]; p += 4
        ex_data = d[p:p + ex]; p += ex
        mask_len = struct.unpack('>I', ex_data[0:4])[0]
        q = 4 + mask_len
        blend_len = struct.unpack('>I', ex_data[q:q + 4])[0]
        q += 4
        name_len = ex_data[q]
        name = ex_data[q + 1:q + 1 + name_len].decode('latin1', errors='replace')
        rest = ex_data[q + 1 + name_len:]
        blocks = []
        k = 0
        while k + 12 <= len(rest):
            if rest[k:k + 4] != b'8BIM':
                break
            key = rest[k + 4:k + 8].decode('latin1', errors='replace')
            ln = struct.unpack('>I', rest[k + 8:k + 12])[0]
            blocks.append(key)
            k += 12 + ln + (ln & 1)
        print('  层%-3d 通道=%-18s 蒙版=%-4d 名=%-22r 附加块=%s'
              % (i + 1, ids, mask_len, name, blocks))


if __name__ == '__main__':
    dump(sys.argv[1])
