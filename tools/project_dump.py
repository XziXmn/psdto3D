import sys, re

def load(path):
    raw = open(path, 'rb').read()
    text = raw.decode('gbk', 'replace')
    lines = re.split(r'\r\n|\r|\n', text)
    if lines and lines[-1] == '':
        lines.pop()
    return raw, lines

for path in sys.argv[1:]:
    raw, lines = load(path)
    print('=' * 100)
    print('%s  (%d bytes, %d lines)' % (path, len(raw), len(lines)))
    for i, ln in enumerate(lines, 1):
        print('%3d | %s' % (i, ln.replace('\t', '<TAB>')[:120]))
