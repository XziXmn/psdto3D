# -*- coding: utf-8 -*-
"""Build cmykdrop/replay_table.h from the `CAP pay` lines of a real-dongle capture.

Each `CAP pay op=DD|D1 addr=XXXX len=N data=<hex>` line is one protocol event:
    op=DD  -> host writes N bytes to the dongle   (payload = request)
    op=D1  -> host reads  N bytes from the dongle (payload = response)

    python tools/gen_replay.py _work/realcap/_dongle.log cmykdrop/replay_table.h
"""
import argparse
import io
import re
import sys

PAY = re.compile(r'CAP pay op=([0-9A-Fa-f]{2}) addr=([0-9A-Fa-f]{4}) len=(\d+) data=([0-9A-Fa-f]*)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('out')
    ap.add_argument('--max', type=int, default=400)
    a = ap.parse_args()

    events = []
    for ln in io.open(a.log, encoding='gbk', errors='replace'):
        m = PAY.search(ln)
        if not m:
            continue
        op = int(m.group(1), 16)
        addr = int(m.group(2), 16)
        n = int(m.group(3))
        raw = m.group(4)
        data = bytes.fromhex(raw) if raw else b''
        if len(data) < n:
            data = data + bytes(n - len(data))
        events.append((op, addr, n, data[:n]))
        if len(events) >= a.max:
            break

    out = ['/* 由 tools/gen_replay.py 从真狗抓包生成，勿手改 */',
           'typedef struct { unsigned char op; unsigned short addr; unsigned len; unsigned char data[501]; } RP_EVENT;',
           '#define RP_N %d' % len(events),
           'static const RP_EVENT g_rp[RP_N] = {']
    for i, (op, addr, n, data) in enumerate(events):
        body = ','.join('0x%02X' % b for b in data)
        out.append('  {/*%d*/ 0x%02X, 0x%04X, %d, {%s}},' % (i, op, addr, n, body))
    out.append('};')
    io.open(a.out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('events=%d -> %s' % (len(events), a.out))
    for i, (op, addr, n, data) in enumerate(events[:10]):
        print('  #%d op=%02X addr=%04X len=%d %s' % (i, op, addr, n, data[:8].hex()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
