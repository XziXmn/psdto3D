"""Convert PSDTO3D project files between the three releases.

Formats (all GBK text, CRLF):

  .tw3d2 / .tw3d   PSDTO3D 10.1 and 2022
      1  <psd path>
      2   <LPI> <Angles> <X> <Depth>
      3  99100 <layerCount> <width> <height>
      4  banner1
      5  banner2
      6  author banner
      7  timestamp  YYYY/M/D H:MM:SS
      8   <DPI>  <LPI2>  <calc> <flag1> <flag2>
      9..        layerCount integers
      ...        layerCount rows  " <angle> <group>  <scale>"
      ...        blocks "<layer> <group> <sub> <points>" + coords + blank

  .gxwj            PSDTO3D 99
      1  <psd path>
      2   <LPI> <Angles> <X> <Depth>
      3  39550 0 0 0
      4  banner1
      5  banner2 (author + &RGB)
      6   <extra float>          (kept from a reference file when converting)
      7   <DPI>  <LPI2>  <calc> <flag1> <flag2>
      8..        layerCount integers
      ...        layerCount rows
      ...        blocks

Usage:
    python project_convert.py in.gxwj --psd "1114/1114/1114 .psd" --out out.tw3d2
    python project_convert.py in.tw3d2 --psd some.psd --out out.gxwj
    python project_convert.py --batch "dir/*.gxwj" --to tw3d2 --psd-map psd_dir
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import struct
import sys
import time

MAGIC_OLD = '39550'
MAGIC_NEW = '99100'
EOL = '\r\n'
DEFAULT_EXTRA_FLOAT = ' 4.63400000000000E+0004'   # value used by the reference 99 project


# ----------------------------------------------------------------- helpers
def read_psd_size(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(26)
        if head[:4] != b'8BPS':
            return 0, 0, 0
        h, w = struct.unpack('>II', head[14:22])
        # layer count lives in the layer info section
        with open(path, 'rb') as f:
            f.seek(26)
            for _ in range(2):
                ln = struct.unpack('>I', f.read(4))[0]
                f.seek(ln, 1)
            lm = struct.unpack('>I', f.read(4))[0]
            n = 0
            if lm >= 4:
                li = struct.unpack('>I', f.read(4))[0]
                if li >= 2:
                    n = abs(struct.unpack('>h', f.read(2))[0])
        return w, h, n
    except Exception:  # noqa: BLE001
        return 0, 0, 0


def fmt_float(v):
    mant, exp = ('%.14E' % v).split('E')
    return '%sE%+05d' % (mant, int(exp))


LAYER_ROW = re.compile(r'^-?\d+ -?\d+  [-+0-9.E]+$')


class Doc:
    def __init__(self):
        self.kind = None          # 'new' | 'old'
        self.psd = ''
        self.psd_alt = ''         # .gxwj keeps an alternate name in some builds
        self.l2 = ''
        self.banners = []
        self.extra_float = DEFAULT_EXTRA_FLOAT
        self.timestamp = ''
        self.l8 = ''
        self.offsets = []
        self.rows = []
        self.tail = []            # everything from the first block to the end
        self.layer_count = 0

    # ------------------------------------------------------------- parsing
    @classmethod
    def load(cls, path):
        text = open(path, 'rb').read().decode('gbk', 'replace')
        lines = re.split(r'\r\n', text)
        if lines and lines[-1] == '':
            lines.pop()
        d = cls()
        d.psd = lines[0]
        d.l2 = lines[1]
        tag = lines[2].split()
        if tag and tag[0] == MAGIC_OLD:
            d.kind = 'old'
            d.banners = lines[3:5]
            d.extra_float = lines[5]
            d.l8 = lines[6]
            start = 7
        else:
            d.kind = 'new'
            d.banners = lines[3:6]
            d.timestamp = lines[6]
            d.l8 = lines[7]
            start = 8
        # offsets: integers until the first layer row
        i = start
        while i < len(lines) and lines[i].strip() and not LAYER_ROW.match(lines[i]):
            try:
                int(lines[i].strip())
            except ValueError:
                break
            d.offsets.append(int(lines[i].strip()))
            i += 1
        while i < len(lines) and LAYER_ROW.match(lines[i]):
            d.rows.append(lines[i])
            i += 1
        d.tail = lines[i:]
        d.layer_count = len(d.rows)
        return d

    def regroup(self):
        """Renumber the layer groups densely (1..k).

        PSDTO3D 10.1/2022 size their per-group tables by the *maximum* group number and
        then walk every slot, so a gap (e.g. groups {2,5}) leaves NULL entries that are
        dereferenced while generating (0x50A001 / 0x5023C7).  PSDTO3D 99 tolerates it.
        """
        used = sorted({int(r.split()[1]) for r in self.rows if 0 < int(r.split()[1]) < 100})
        mapping = {old: i + 1 for i, old in enumerate(used)}
        if all(mapping.get(k, k) == k for k in used):
            return []
        changed = []
        new_rows = []
        for r in self.rows:
            parts = r.split()
            old = int(parts[1])
            new = mapping.get(old, old)
            if new != old:
                pos = r.index(parts[1])
                r = r[:pos] + str(new) + r[pos + len(parts[1]):]
                changed.append((old, new))
            new_rows.append(r)
        self.rows = new_rows
        return changed

    # ------------------------------------------------------------ writing
    def to_new(self, psd_path=None, width=None, height=None, layer_count=None, regroup=False):
        psd = psd_path or self.psd
        if regroup:
            self.regroup()
        n = layer_count or self.layer_count
        w = width if width is not None else 0
        h = height if height is not None else 0
        banners = list(self.banners) + [''] * (3 - len(self.banners))
        author = banners[2] if banners[2] else 'Author: '
        ts = self.timestamp or time.strftime('%Y/%m/%d %H:%M:%S')
        out = [psd, self.l2, '%s %d %d %d' % (MAGIC_NEW, n, w, h),
               banners[0], banners[1], author, ts, self.l8]
        out += [str(v) for v in self.offsets[:n]]
        out += self.rows[:n]
        out += self.tail
        text = EOL.join(out)
        # .gxwj files carry a stray CR before the CRLF of every coordinate line;
        # the 10.1/2022 parser answers "Invalid numeric input" on those, so drop it.
        return text.replace('\r\r\n', '\r\n')

    def to_old(self, psd_path=None):
        psd = psd_path or self.psd
        out = [psd, self.l2, '%s 0 0 0' % MAGIC_OLD,
               self.banners[0] if self.banners else '',
               self.banners[1] if len(self.banners) > 1 else '',
               self.extra_float, self.l8]
        out += [str(v) for v in self.offsets[:self.layer_count]]
        out += self.rows
        out += self.tail
        return EOL.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src', nargs='?')
    ap.add_argument('--psd', default=None, help='new PSD path written into the project')
    ap.add_argument('--out', default=None)
    ap.add_argument('--to', choices=['tw3d2', 'gxwj'], default=None)
    ap.add_argument('--batch', default=None)
    ap.add_argument('--layer-count', type=int, default=None)
    ap.add_argument('--no-regroup', action='store_true',
                    help='keep the original group numbers (99 accepts them, 10.1/2022 do not)')
    a = ap.parse_args()

    if a.batch:
        files = [p for p in glob.glob(a.batch) if os.path.isfile(p)]
        for p in files:
            d = Doc.load(p)
            dest_ext = {'tw3d2': '.tw3d2', 'gxwj': '.gxwj'}[a.to]
            out = os.path.splitext(p)[0] + dest_ext
            text = d.to_new(a.psd) if a.to == 'tw3d2' else d.to_old(a.psd)
            open(out, 'wb').write(text.encode('gbk', 'replace'))
            print('%-34s -> %-34s (%d layers)' % (os.path.basename(p), os.path.basename(out), d.layer_count))
        return 0

    d = Doc.load(a.src)
    target = a.to or ('gxwj' if d.kind == 'new' else 'tw3d2')
    psd = a.psd or d.psd
    w = h = n = None
    if os.path.isfile(psd):
        w, h, n = read_psd_size(psd)
    if target == 'tw3d2':
        text = d.to_new(psd, w, h, a.layer_count or (n or d.layer_count),
                        regroup=not a.no_regroup)
    else:
        text = d.to_old(psd)
    out = a.out or (os.path.splitext(a.src)[0] + ('.tw3d2' if target == 'tw3d2' else '.gxwj'))
    open(out, 'wb').write(text.encode('gbk', 'replace'))
    print('written %s (%s, layers=%d, psd=%s)' % (out, target, d.layer_count, psd))
    return 0


if __name__ == '__main__':
    sys.exit(main())
