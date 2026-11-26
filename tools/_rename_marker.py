# -*- coding: utf-8 -*-
"""把标记改成更好懂的名字：_layers_up.txt（同时兼容旧的 _layerstr.txt）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if '_layers_up.txt' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''        if (GetFileAttributesA("_layerstr.txt") != INVALID_FILE_ATTRIBUTES)
            alloc_layer_strs();'''
NEW = '''        if (GetFileAttributesA("_layers_up.txt") != INVALID_FILE_ATTRIBUTES ||
            GetFileAttributesA("_layerstr.txt") != INVALID_FILE_ATTRIBUTES)
            alloc_layer_strs();'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
