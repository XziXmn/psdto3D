# -*- coding: utf-8 -*-
"""检查工程文件里"应该都是数字"的行有没有异常 token。"""
import io
import re
import sys

NUM = re.compile(r'^[+-]?(\d+)(\.\d+)?([Ee][+-]?\d+)?$')


def check(path, start):
    d = io.open(path, 'rb').read().decode('gbk', errors='replace').split('\r\n')
    bad = []
    for i in range(start, len(d)):
        line = d[i]
        if not line.strip():
            continue
        for tok in line.split():
            if not NUM.match(tok):
                bad.append((i, tok, line[:70]))
                break
    print('%-40s 行数 %d，可疑 %d' % (path.split('\\')[-1], len(d), len(bad)))
    for i, tok, line in bad[:10]:
        print('   行%-5d token=%-14r %r' % (i, tok, line))


if __name__ == '__main__':
    for p in sys.argv[1:]:
        check(p, 8)
