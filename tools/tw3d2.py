"""Reader / writer / repair tool for PSDTO3D project files (*.tw3d2, *.tw3d).

The format was recovered from the shipped samples of PSDTO3D 10.1 and 2022
(see docs/工程文件格式.md).  It is plain text: GBK-encoded, CRLF separated.

Layout
------
  L1                     absolute path of the source PSD
  L2   " <LPI> <Angles> <X> <Depth>"        floats/ints, space padded
  L3   "99100 <layerCount> <width> <height>"
  L4                     company / e-mail banner
  L5                     mobile phone banner
  L6                     author banner
  L7                     save timestamp  "YYYY/M/D H:MM:SS"
  L8   " <DPI> <LPI2> <calc> <flag1> <flag2>"
  L9..                   layerCount integers (per-layer offset)
  ...                    layerCount lines " <angle> <group>  <scale>"
  ...                    free-draw blocks:
                            "<layer> <group> <sub> <pointCount>"
                            "<x1> <y1> <x2> <y2> ... "
                            ""                       (blank line)
  trailing blank line

`load()` keeps the original lines, so `save()` reproduces the file byte for byte
(verified on every shipped sample of both versions).
"""
from __future__ import annotations

import argparse
import os
import re
import sys

MAGIC = '99100'
EOL = '\r\n'


def _num(tok: str) -> float:
    return float(tok.replace(',', '.'))


def _fmt_float(value: float) -> str:
    """Delphi's FloatToStr style used by the app: 5.30000000000000E+0001

    Mantissa with 14 decimals, no leading sign, exponent padded to four digits.
    """
    mant, exp = ('%.14E' % value).split('E')
    return '%sE%+05d' % (mant, int(exp))


class Layer:
    __slots__ = ('angle', 'group', 'scale', 'residue')

    def __init__(self, angle, group, scale, residue=''):
        self.angle = angle
        self.group = group
        self.scale = scale
        self.residue = residue

    def __str__(self):
        return '%d %d  %s%s' % (self.angle, self.group, self.scale, self.residue)


class Block:
    __slots__ = ('layer', 'group', 'sub', 'points')

    def __init__(self, layer, group, sub, points):
        self.layer = layer
        self.group = group
        self.sub = sub
        self.points = points

    def __str__(self):
        pts = ' '.join('%d %d' % p for p in self.points)
        return '%d %d %d %d' % (self.layer, self.group, self.sub, len(self.points)) + EOL + pts + ' ' + EOL


class Project:
    def __init__(self):
        self.psd_path = ''
        self.lpi = 0.0
        self.angles = 0
        self.x_field = 0
        self.depth = 0.0
        self.layer_count = 0
        self.width = 0
        self.height = 0
        self.banner = ['', '', '']
        self.timestamp = ''
        self.dpi = 0.0
        self.lpi2 = 0.0
        self.calc = 0.0
        self.flag1 = 0
        self.flag2 = 0
        self.offsets = []
        self.layers = []
        self.blocks = []
        self.raw = None          # original text, for exact round-trip
        self.lines = None        # original lines, edited in place on save
        self._dirty = set()      # which header lines were changed
        self.source = None

    # ---------------------------------------------------------------- load
    @classmethod
    def load(cls, path):
        raw = open(path, 'rb').read()
        text = raw.decode('gbk', 'replace')
        lines = re.split(r'\r\n', text)
        p = cls()
        p.source = path
        p.raw = text
        p.lines = lines
        p.psd_path = lines[0]
        f2 = lines[1].split()
        p.lpi, p.angles, p.x_field, p.depth = _num(f2[0]), int(f2[1]), int(f2[2]), _num(f2[3])
        f3 = lines[2].split()
        p.layer_count, p.width, p.height = int(f3[1]), int(f3[2]), int(f3[3])
        p.banner = lines[3:6]
        p.timestamp = lines[6]
        f8 = lines[7].split()
        p.dpi, p.lpi2, p.calc = _num(f8[0]), _num(f8[1]), _num(f8[2])
        p.flag1, p.flag2 = int(f8[3]), int(f8[4])
        idx = 8
        p.offsets = [int(lines[idx + i].strip()) for i in range(p.layer_count)]
        idx += p.layer_count
        p.layers = []
        for i in range(p.layer_count):
            tok = lines[idx + i].split()
            rest = lines[idx + i]
            tail = rest[rest.index(tok[2]) + len(tok[2]):] if len(tok) > 2 else ''
            p.layers.append(Layer(int(tok[0]), int(tok[1]), tok[2], tail))
        idx += p.layer_count
        while idx < len(lines) - 1:
            line = lines[idx].strip()
            if not line:
                idx += 1
                continue
            head = line.split()
            if len(head) == 4 and all(re.fullmatch(r'-?\d+', t) for t in head):
                layer, group, sub, count = (int(t) for t in head)
                pts_raw = lines[idx + 1].split() if idx + 1 < len(lines) else []
                coords = [int(t) for t in pts_raw if re.fullmatch(r'-?\d+', t)]
                pts = [(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
                p.blocks.append(Block(layer, group, sub, pts))
                idx += 2
                if count != len(pts):
                    p.blocks[-1].sub = sub          # keep as written
            else:
                idx += 1
        return p

    # ---------------------------------------------------------------- save
    def text(self):
        """Serialise the project.

        When the project was loaded from a file the original lines are reused and
        only the header lines that were actually changed are rewritten, so a
        repair never disturbs the layer/curve sections of a legacy file.
        """
        if self.lines is not None:
            out = list(self.lines)
            if 'psd' in self._dirty:
                out[0] = self.psd_path
            if 'geom' in self._dirty:
                out[1] = ' %s %d %d  %s' % (_fmt_float(self.lpi), self.angles, self.x_field,
                                            _fmt_float(self.depth))
            if 'count' in self._dirty:
                out[2] = '%s %d %d %d' % (MAGIC, self.layer_count, self.width, self.height)
            if 'save8' in self._dirty:
                out[7] = ' %s  %s  %s %d %d' % (_fmt_float(self.dpi), _fmt_float(self.lpi2),
                                                _fmt_float(self.calc), self.flag1, self.flag2)
            return EOL.join(out)
        out = [
            self.psd_path,
            ' %s %d %d  %s' % (_fmt_float(self.lpi), self.angles, self.x_field, _fmt_float(self.depth)),
            '%s %d %d %d' % (MAGIC, self.layer_count, self.width, self.height),
            *self.banner,
            self.timestamp,
            ' %s  %s  %s %d %d' % (_fmt_float(self.dpi), _fmt_float(self.lpi2), _fmt_float(self.calc),
                                   self.flag1, self.flag2),
        ]
        out += [str(v) for v in self.offsets[:self.layer_count]]
        out += [str(layer) for layer in self.layers[:self.layer_count]]
        for b in self.blocks:
            out.append(str(b))
            out.append('')
        return EOL.join(out) + EOL

    def save(self, path, verify_roundtrip=False):
        text = self.text()
        with open(path, 'wb') as f:
            f.write(text.encode('gbk', 'replace'))
        if verify_roundtrip and self.raw is not None:
            return text == self.raw
        return None

    # ------------------------------------------------------------- helpers
    def retarget(self, psd_path):
        self.psd_path = psd_path
        self._dirty.add('psd')

    def set_angles(self, angles):
        self.angles = int(angles)
        self._dirty.add('geom')

    def set_layer_count(self, count):
        self.layer_count = int(count)
        self._dirty.add('count')

    def problems(self):
        out = []
        if not self.psd_path:
            out.append('PSD 路径为空')
        else:
            exists = os.path.isfile(self.psd_path)
            if not exists:
                out.append('PSD 路径不存在：%s（跨机器一定会踩到）' % self.psd_path)
        if self.angles <= 0:
            out.append('Angles(L2 第 2 个字段)=%d ≤ 0 → 生成视图时会除以 0，触发 EInvalidOp/AV' % self.angles)
        if self.layer_count <= 0:
            out.append('layerCount=0 → 图层数组为空，3D 生成循环会解引用 NULL')
        if len(self.offsets) != self.layer_count:
            out.append('offset 行数 %d 与 layerCount %d 不一致' % (len(self.offsets), self.layer_count))
        if len(self.layers) != self.layer_count:
            out.append('图参数行数 %d 与 layerCount %d 不一致' % (len(self.layers), self.layer_count))
        for b in self.blocks:
            if not (0 <= b.layer < self.layer_count):
                out.append('绘制块引用越界图层 %d（共 %d 层）' % (b.layer, self.layer_count))
                break
        if self.flag1 not in (1, 2):
            out.append('L8 flag1=%d（样本只有 1/2）' % self.flag1)
        return out

    def summary(self):
        return {
            'psd': self.psd_path,
            'lpi': self.lpi,
            'angles': self.angles,
            'depth': self.depth,
            'layers': self.layer_count,
            'size': '%dx%d' % (self.width, self.height),
            'dpi': self.dpi,
            'lpi2': self.lpi2,
            'flags': [self.flag1, self.flag2],
            'offsets': len(self.offsets),
            'layer_lines': len(self.layers),
            'blocks': len(self.blocks),
            'timestamp': self.timestamp,
        }


def cmd_dump(args):
    p = Project.load(args.project)
    for k, v in p.summary().items():
        print('%-12s %s' % (k, v))
    probs = p.problems()
    print('problems   %s' % ('(none)' if not probs else ''))
    for x in probs:
        print('   - %s' % x)


def cmd_check(args):
    import psdinfo
    bad = 0
    for path in args.projects:
        p = Project.load(path)
        probs = p.problems()
        note = ''
        if args.psd and os.path.isfile(p.psd_path):
            try:
                h = psdinfo.read_psd_header(p.psd_path)
                note = ' | PSD %dx%d layers=%s' % (h.width, h.height, h.layers)
                if h.layers is not None and h.layers != p.layer_count:
                    probs = probs + ['图层数不一致：工程 %d / PSD %d（索引对不上，生成时会崩）'
                                     % (p.layer_count, h.layers)]
                if (h.width, h.height) != (p.width, p.height):
                    probs = probs + ['尺寸不一致：工程 %dx%d / PSD %dx%d'
                                     % (p.width, p.height, h.width, h.height)]
            except Exception as exc:  # noqa: BLE001
                note = ' | PSD unreadable: %s' % exc
        print('%s  layers=%d angles=%d blocks=%d%s  %s' %
              (os.path.basename(path), p.layer_count, p.angles, len(p.blocks), note,
               'OK' if not probs else 'ISSUES'))
        for x in probs:
            print('    - %s' % x)
        bad += bool(probs)
    return 1 if bad and args.strict else 0


def cmd_roundtrip(args):
    ok = 0
    for path in args.projects:
        p = Project.load(path)
        out = p.text()
        same = out == p.raw
        print('%-32s %s' % (os.path.basename(path), 'identical' if same else 'DIFFERS'))
        ok += same
    print('%d/%d byte-identical round trips' % (ok, len(args.projects)))
    return 0 if ok == len(args.projects) else 1


def cmd_retarget(args):
    p = Project.load(args.project)
    p.retarget(args.psd)
    if args.angles is not None:
        p.set_angles(args.angles)
    if args.layer_count is not None:
        p.set_layer_count(args.layer_count)
    if args.fix_counts:
        p.set_layer_count(min(len(p.offsets), len(p.layers)))
    out = args.out or args.project
    p.save(out)
    print('written %s  (psd -> %s, layers=%d, angles=%d)' % (out, p.psd_path, p.layer_count, p.angles))
    for x in p.problems():
        print('   ! %s' % x)


def cmd_regroup(args):
    """Renumber layer groups densely (1..k) so the generator's group table has no holes.

    PSDTO3D 2022 sizes its per-group tables by the *maximum* group value and then
    walks every slot; a missing group leaves a nil entry that is dereferenced while
    interleaving (the 0x50A001 access violation).  Densifying the numbering keeps the
    grouping semantics (layers that shared a group still share one) and removes the
    holes.  Group 0 and values >= 100 are left alone: the app skips them by design.
    """
    changed = 0
    for path in args.projects:
        p = Project.load(path)
        used = sorted({layer.group for layer in p.layers if 0 < layer.group < 100})
        mapping = {old: i + 1 for i, old in enumerate(used)}
        if all(mapping.get(old, old) == old for old in used):
            print('%-32s already dense %s' % (os.path.basename(path), used))
            continue
        if p.lines is None:
            print('%-32s not loaded from a file' % os.path.basename(path))
            continue
        start = 8 + p.layer_count
        for i in range(p.layer_count):
            idx = start + i
            line = p.lines[idx]
            parts = line.split()
            if len(parts) < 2:
                continue
            old = int(parts[1])
            new = mapping.get(old, old)
            if new == old:
                continue
            pos = line.index(parts[1])
            p.lines[idx] = line[:pos] + str(new) + line[pos + len(parts[1]):]
        out = args.out or path
        with open(out, 'wb') as f:
            f.write(p.text().encode('gbk', 'replace'))
        print('%-32s groups %s -> 1..%d  (%s)' %
              (os.path.basename(path), used, len(used), out))
        changed += 1
    print('%d file(s) rewritten' % changed)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    d = sub.add_parser('dump', help='print the decoded header of one project')
    d.add_argument('project')
    d.set_defaults(func=cmd_dump)

    c = sub.add_parser('check', help='report consistency problems of one or more projects')
    c.add_argument('projects', nargs='+')
    c.add_argument('--strict', action='store_true')
    c.add_argument('--psd', action='store_true', help='also compare against the referenced PSD header')
    c.set_defaults(func=cmd_check)

    r = sub.add_parser('roundtrip', help='verify that parse+serialise is lossless')
    r.add_argument('projects', nargs='+')
    r.set_defaults(func=cmd_roundtrip)

    t = sub.add_parser('retarget', help='rewrite the PSD path / fix counts of a project')
    t.add_argument('project')
    t.add_argument('--psd', required=True, help='new PSD path (absolute, or relative to the project)')
    t.add_argument('--angles', type=int, default=None)
    t.add_argument('--layer-count', type=int, default=None)
    t.add_argument('--fix-counts', action='store_true', help='set layerCount from parsed rows')
    t.add_argument('--out', default=None)
    t.set_defaults(func=cmd_retarget)

    g = sub.add_parser('regroup', help='renumber layer groups densely (avoids the 0x50A001 crash)')
    g.add_argument('projects', nargs='+')
    g.add_argument('--out', default=None)
    g.set_defaults(func=cmd_regroup)

    args = ap.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == '__main__':
    main()
