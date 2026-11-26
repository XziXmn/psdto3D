# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\tools\open99_50layer.py'
s = io.open(P, encoding='utf-8').read()
s = s.replace("os.path.join(PKG, 'p50.gxwj')", "os.path.join(PKG, 'p50fix.gxwj')")
io.open(P, 'w', encoding='utf-8').write(s)
print('target -> p50fix.gxwj')
