"""Make every sample project inside a package self-contained: point its PSD path
at the copy of the PSD that ships next to the project file."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tw3d2


def main(pkg):
    sample = os.path.join(pkg, 'sample')
    if not os.path.isdir(sample):
        print('no sample dir in', pkg)
        return 1
    psds = {os.path.basename(p).lower(): p for p in
            (os.path.join(sample, n) for n in os.listdir(sample)) if p.lower().endswith('.psd')}
    changed = 0
    for name in sorted(os.listdir(sample)):
        if not name.lower().endswith(('.tw3d2', '.tw3d')):
            continue
        path = os.path.join(sample, name)
        proj = tw3d2.Project.load(path)
        want = os.path.basename(proj.psd_path).lower()
        target = psds.get(want)
        if not target:
            print('  skip %-28s (PSD %s not in package)' % (name, os.path.basename(proj.psd_path)))
            continue
        if os.path.normcase(os.path.abspath(proj.psd_path)) == os.path.normcase(os.path.abspath(target)):
            print('  ok   %-28s' % name)
            continue
        proj.retarget(target)
        proj.save(path)
        changed += 1
        print('  fix  %-28s -> %s' % (name, os.path.basename(target)))
    print('%s: %d project(s) retargeted' % (pkg, changed))
    return 0


if __name__ == '__main__':
    for pkg in sys.argv[1:]:
        main(pkg)
