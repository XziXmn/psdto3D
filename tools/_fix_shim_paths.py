# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'g_native_file' in s:
    print('already patched')
    raise SystemExit(0)

s = s.replace('static PF_WRITEPSD o_writepsd;',
              'static PF_WRITEPSD o_writepsd;\r\nstatic char g_native_file[MAX_PATH], g_native_dir[MAX_PATH];', 1)

OLD1 = '    slot = (void **)((char *)GetModuleHandleA(0) + 0x123278);'
NEW1 = ('    lstrcpynA(g_native_file, file ? file : "", MAX_PATH);\r\n'
        '    lstrcpynA(g_native_dir, dir ? dir : "", MAX_PATH);\r\n'
        + OLD1)
assert OLD1 in s, 'slot anchor missing'
s = s.replace(OLD1, NEW1, 1)

OLD2 = ('    if (file && dir && layers > 0 && layers <= 64 && w > 0 && h > 0)\r\n'
        '        psd_assemble(file, dir, w, h, layers);')
NEW2 = ('    if (g_native_file[0] && g_native_dir[0] && layers > 0 && layers <= 64 && w > 0 && h > 0)\r\n'
        '        psd_assemble(g_native_file, g_native_dir, w, h, layers);')
if OLD2 in s:
    s = s.replace(OLD2, NEW2, 1)
else:
    s = s.replace('        psd_assemble(file, dir, w, h, layers);',
                  '        psd_assemble(g_native_file, g_native_dir, w, h, layers);', 1)

io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
