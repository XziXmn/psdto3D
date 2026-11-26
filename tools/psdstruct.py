"""只读地解剖一个 PSD：头部、层段结构、每层的名称/通道/矩形/压缩方式。

用途：复查参照物与产出是否同构。不修改任何文件。

实测（2026-11-18 复核）：psdto3d 写出的 PSD 把**全部层记录连续放在层段开头**，
之后才是各层的通道像素数据；这与 Adobe 规范（记录与数据逐层交错）不同。
本脚本按实测布局解析，并报告"层记录结束位置/通道数据起点"。

    python tools/psdstruct.py FILE [--layers N] [--json]
"""
import argparse
import json
import mmap
import struct
import sys


def _keys(d, p, ex_end):
    """读 additional layer info：8BIM/8B64 + key + len + data。"""
    out = []
    while p + 12 <= ex_end:
        if d[p:p + 4] not in (b'8BIM', b'8B64'):
            break
        key = bytes(d[p + 4:p + 8]).decode('latin1')
        klen, = struct.unpack_from('>I', d, p + 8)
        val = bytes(d[p + 12:p + 12 + klen])
        out.append({'key': key, 'len': klen, 'val': val})
        p += 12 + klen + (klen % 2)
    return out


def _unicode_name(keys):
    for k in keys:
        if k['key'] == 'luni':
            v = k['val']
            if len(v) >= 4:
                n, = struct.unpack_from('>H', v, 0)          # 实测：2 字节长度（非规范 4 字节）
                body = v[2:2 + n * 2]
            else:
                n, body = 0, b''
            if 0 < n < 64:
                return body.decode('utf-16-be', 'replace')
            n, = struct.unpack_from('>I', v, 0)              # 规范写法：4 字节长度
            body = v[4:4 + n * 2]
            return body.decode('utf-16-be', 'replace')
    return None


def parse(path, max_layers=40):
    out = {'file': path}
    with open(path, 'rb') as f:
        n = max(1, f.seek(0, 2))
        f.seek(0)
        d = mmap.mmap(f.fileno(), n, access=mmap.ACCESS_READ)
        try:
            return _parse(path, d, max_layers)
        finally:
            d.close()


def _parse(path, d, max_layers=40):
    out = {'file': path, 'size': len(d)}
    if d[:4] != b'8BPS':
        out['error'] = 'not 8BPS: %r' % bytes(d[:4])
        return out
    ver, = struct.unpack_from('>H', d, 4)
    ch, h, w, depth, mode = struct.unpack_from('>HIIHH', d, 12)
    out.update(version=ver, channels=ch, height=h, width=w, depth=depth, mode=mode)

    p = 26
    n, = struct.unpack_from('>I', d, p)
    p += 4 + n                                    # color mode data
    n, = struct.unpack_from('>I', d, p)
    p += 4 + n                                    # image resources
    lm_len, = struct.unpack_from('>I', d, p)
    out['layer_mask_len'] = lm_len
    p += 4
    out['layers'] = []
    out['layer_count'] = 0
    if lm_len == 0:
        return out
    li_len, = struct.unpack_from('>I', d, p)
    out['layer_info_len'] = li_len
    p += 4
    li_end = p + li_len
    cnt, = struct.unpack_from('>h', d, p)
    p += 2
    out['layer_count_raw'] = cnt
    out['layer_count'] = abs(cnt)

    layers = []
    for i in range(min(abs(cnt), max_layers)):
        top, left, bottom, right = struct.unpack_from('>iiii', d, p)
        p += 16
        nch, = struct.unpack_from('>H', d, p)
        p += 2
        chans = []
        for _ in range(nch):
            cid, clen = struct.unpack_from('>hI', d, p)
            p += 6
            chans.append({'id': cid, 'len': clen})
        blend = bytes(d[p + 4:p + 8]).decode('latin1')
        opacity, clipping, flags, _f = struct.unpack_from('>BBBB', d, p + 8)
        p += 12
        exlen, = struct.unpack_from('>I', d, p)
        p += 4
        ex_end = p + exlen
        q = p
        mask_len, = struct.unpack_from('>I', d, q)
        q += 4 + mask_len
        br_len, = struct.unpack_from('>I', d, q)
        q += 4 + br_len
        nlen = d[q]
        name = bytes(d[q + 1:q + 1 + nlen]).decode('gbk', 'replace')
        q += ((1 + nlen + 3) // 4) * 4
        keys = _keys(d, q, ex_end)
        uni = _unicode_name(keys)
        if uni:
            name = uni
        px = (right - left) * (bottom - top)
        layers.append({
            'idx': i, 'name': name, 'rect': [top, left, bottom, right],
            'w': right - left, 'h': bottom - top, 'px': px,
            'channels': chans,
            'data_bytes': sum(c['len'] for c in chans),
            'blend': blend, 'opacity': opacity, 'flags': flags,
            'mask_len': mask_len, 'blendranges_len': br_len, 'extra_len': exlen,
            'keys': ['%s:%d' % (k['key'], k['len']) for k in keys],
        })
        p = ex_end                               # 实测布局：记录连续，数据在后面
    out['layers'] = layers
    out['records_end'] = p
    out['channel_data_bytes'] = sum(L['data_bytes'] for L in layers)
    out['records_overhead'] = p - 44
    out['li_end'] = li_end
    rest = len(d) - li_end - 16
    out['trailing_after_layerinfo'] = len(d) - li_end
    if h and w and ch:
        out['composite_unc'] = h * w * ch * (depth // 8)
        out['composite_fits'] = rest >= out['composite_unc'] or rest >= 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--layers', type=int, default=40)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    r = parse(a.file, a.layers)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    print('== %s' % r['file'])
    print('size=%s %s ver=%s %sx%s ch=%s depth=%s mode=%s' % (
        r['size'], r.get('error', ''), r.get('version'), r.get('width'), r.get('height'),
        r.get('channels'), r.get('depth'), r.get('mode')))
    print('layers=%s raw=%s li_len=%s records_end=%s overhead=%s chan_bytes=%s trailing=%s composite_unc=%s' % (
        r.get('layer_count'), r.get('layer_count_raw'), r.get('layer_info_len'),
        r.get('records_end'), r.get('records_overhead'), r.get('channel_data_bytes'),
        r.get('trailing_after_layerinfo'), r.get('composite_unc')))
    seen = {}
    for L in r['layers']:
        seen[(L['w'], L['h'], tuple(c['id'] for c in L['channels']),
              tuple(c['len'] for c in L['channels']))] = seen.get(
            (L['w'], L['h'], tuple(c['id'] for c in L['channels']),
             tuple(c['len'] for c in L['channels'])), 0) + 1
        print('  [%02d] %-10s %4dx%-4d rect=%s ch=%s data=%d keys=%s' % (
            L['idx'], L['name'], L['w'], L['h'], L['rect'],
            ','.join('%d/%d' % (c['id'], c['len']) for c in L['channels']),
            L['data_bytes'], ','.join(L['keys']) if L['keys'] else '-'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
