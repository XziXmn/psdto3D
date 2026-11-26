# -*- coding: utf-8 -*-
"""复制工程并把线数（第二行第二个字段）改成指定值。"""
import io
import sys

SRC = r'C:\bio\a.tw3d2'
DST = sys.argv[1] if len(sys.argv) > 1 else r'C:\bio\a13.tw3d2'
LINES = int(sys.argv[2]) if len(sys.argv) > 2 else 13

data = io.open(SRC, 'rb').read().decode('gbk', errors='replace')
parts = data.split('\r\n')
toks = parts[1].split(' ')
# ['', '2.52E+01', '11', '13', '', '1.8E+00']
toks[2] = str(LINES)
parts[1] = ' '.join(toks)
io.open(DST, 'wb').write('\r\n'.join(parts).encode('gbk', errors='replace'))
print('原:', repr(data.split('\r\n')[1]))
print('新:', repr(parts[1]))
print('写出', DST)
