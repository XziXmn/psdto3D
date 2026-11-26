# -*- coding: utf-8 -*-
"""Rebuild cmykdrop/replay_table.h from a CAP capture log.

The emulator logs, in order:

    CAP wf n=<len> got=<g> data=<hex 501 字节以内>     ; 主机写（请求负载）
    CAP rf n=<len> got=<g> data=<hex 501 字节以内>     ; 主机读（狗的回答）

plus `CAP dio op=DD addr=XXXX dtl=N` / `op=D1 ...` lines describing the SCSI op.

Strategy: use the `dio` lines as the authoritative op/addr/len sequence, and attach
payloads from the matching wf/rf records in order.

    python tools/gen_replay_from_capture.py _work/realcap/_dongle.log
"""
import argparse
import io
import re
import sys

DIO = re.compile(r'CAP dio op=([0-9A-Fa-f]{2}) addr=([0-9A-Fa-f]{4}) dtl=(\d+)')
WF = re.compile(r'CAP (wf|rf) n=(\d+) got=(\d+) data=([0-9A-Fa-f]*)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--out', default=r'cmykdrop/replay_table_gen.h')
    ap.add_argument('--max-events', type=int, default=200)
    a = ap.parse_args()

    lines = io.open(a.log, encoding='gbk', errors='replace').read().splitlines()

    ops = []
    payloads = []
    for ln in lines:
        m = DIO.search(ln)
        if m:
            ops.append((int(m.group(1), 16), int(m.group(2), 16), int(m.group(3))))
            continue
        m = WF.search(ln)
        if m:
            kind, n, got, data = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            payloads.append((kind, n, bytes.fromhex(data) if data else b''))

    # 仅保留 op=DD / op=D1（读写命令），并按出现顺序配对负载
    pi = 0
    events = []
    for op, addr, dtl in ops:
        if op not in (0xDD, 0xD1):
            continue
        want = dtl if op == 0xDD else dtl
        data = b''
        while pi < len(payloads):
            kind, n, d = payloads[pi]
            pi += 1
            if n == want or (want == 0):
                data = d
                break
        events.append((op, addr, want, data))
        if len(events) >= a.max_events:
            break

    out = ['/* 由 tools/gen_replay_from_capture.py 自动生成 */',
           '#define RP_N %d' % len(events),
           'static const RP_EVENT g_rp[RP_N] = {']
    for i, (op, addr, dtl, data) in enumerate(events):
        body = ','.join('0x%02X' % b for b in data[:dtl]) if data else '0'
        out.append('  {/*%d*/ 0x%02X, 0x%04X, %d, {%s}},' % (i, op, addr, dtl, body))
    out.append('};')
    io.open(a.out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('events=%d  payload_bytes=%d  -> %s' % (len(events), sum(len(d) for *_, d in events), a.out))
    for i, (op, addr, dtl, data) in enumerate(events[:8]):
        print('  #%d op=%02X addr=%04X dtl=%d data=%dB' % (i, op, addr, dtl, len(data)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
