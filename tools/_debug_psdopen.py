# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'PSD open seen' in s:
    print('already there')
    raise SystemExit(0)

OLD = '''    if (name && GetFileAttributesA("_psd_limit.txt") != INVALID_FILE_ATTRIBUTES) {
        int len = lstrlenA(name);
        if (len > 4 && lstrcmpiA(name + len - 4, ".psd") == 0 && psd_layers_guard(name))'''
NEW = '''    if (name) {
        int l2 = lstrlenA(name);
        if (l2 > 4 && lstrcmpiA(name + l2 - 4, ".psd") == 0)
            note("PSD open seen: %s (limit=%d)", name,
                 GetFileAttributesA("_psd_limit.txt") != INVALID_FILE_ATTRIBUTES);
    }
    if (name && GetFileAttributesA("_psd_limit.txt") != INVALID_FILE_ATTRIBUTES) {
        int len = lstrlenA(name);
        if (len > 4 && lstrcmpiA(name + len - 4, ".psd") == 0 && psd_layers_guard(name))'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched')
