"""Make a PSDTO3D project openable on any machine / build.

The three releases all store an *absolute* PSD path inside the project, and none of
them can handle a path that contains spaces ("Can not found the specified psd file!"
or an access violation).  This tool:

  1. looks for the PSD next to the project (basename match, case-insensitive),
     then in --psd-dir, then at the recorded path;
  2. if the PSD name contains spaces, copies it to a space-free name beside it;
  3. rewrites the project's first line to the new (space-free) absolute path;
  4. optionally converts the project between .tw3d2 and .gxwj.

    python fix_project_psd.py "1114/1114/1114 -1.gxwj" --to tw3d2
    python fix_project_psd.py "proj.tw3d2" --psd-dir "D:/psd" --to gxwj
"""
import argparse
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project_convert as pc


def find_psd(project_path, recorded, psd_dir=None):
    base = os.path.basename(recorded)
    project_dir = os.path.dirname(os.path.abspath(project_path))
    candidates = [os.path.join(project_dir, base)]
    if psd_dir:
        candidates.append(os.path.join(psd_dir, base))
    if os.path.isabs(recorded):
        candidates.append(recorded)
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    # try any PSD in the project folder whose name shares the stem
    stem = os.path.splitext(base)[0].strip().lower()
    if os.path.isdir(project_dir):
        for n in os.listdir(project_dir):
            if n.lower().endswith('.psd') and stem and stem.split(' ')[0] in n.lower():
                return os.path.join(project_dir, n)
    return None


def make_spacefree(psd_path):
    d, name = os.path.split(psd_path)
    if ' ' not in name:
        return psd_path
    clean = re.sub(r'\s+', '', name)
    target = os.path.join(d, clean)
    if not os.path.isfile(target):
        shutil.copy2(psd_path, target)
    return target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--psd-dir', default=None)
    ap.add_argument('--to', choices=['tw3d2', 'gxwj'], default=None)
    ap.add_argument('--out', default=None)
    ap.add_argument('--no-copy', action='store_true', help='do not create a space-free PSD copy')
    a = ap.parse_args()

    doc = pc.Doc.load(a.project)
    psd = find_psd(a.project, doc.psd, a.psd_dir)
    if not psd:
        print('PSD not found for %s (recorded: %s)' % (os.path.basename(a.project), doc.psd))
        return 2
    if not a.no_copy:
        psd2 = make_spacefree(psd)
        if psd2 != psd:
            print('space-free copy: %s' % os.path.basename(psd2))
        psd = psd2
    w, h, n = pc.read_psd_size(psd)
    print('psd=%s  %dx%d  layers=%d' % (psd, w, h, n))

    target = a.to or ('tw3d2' if doc.kind == 'old' else 'gxwj')
    if target == 'tw3d2':
        text = doc.to_new(psd, w, h, n or doc.layer_count, regroup=True)
        ext = '.tw3d2'
    else:
        text = doc.to_old(psd)
        ext = '.gxwj'
    out = a.out or (os.path.splitext(a.project)[0] + '_fixed' + ext)
    open(out, 'wb').write(text.encode('gbk', 'replace'))
    print('written %s (%s, layers=%d)' % (out, target, doc.layer_count))
    return 0


if __name__ == '__main__':
    sys.exit(main())
