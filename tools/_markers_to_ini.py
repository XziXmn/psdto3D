# -*- coding: utf-8 -*-
"""把 "_xxx.txt 标记文件" 换成 ini 配置项（同时保留旧标记文件作为兼容）。

    [green]
    native_psd=1
    ...
"""
import io
import re

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cfg_on(' in s:
    print('already patched')
    raise SystemExit(0)

# 用户功能（默认开） / 调试钩子（默认关）
DEFAULTS = {
    'native_psd': 1, 'inject_x2': 1, 'gxwj': 1, 'fix_cancel': 1, 'layers_up': 1,
    'psd_limit': 0, 'psd_build': 0, 'cn_ui': 0, 'cn_native': 0,
}

HELPER = r'''
/* ================= 配置：psdto3d_green.ini（旧版 _xxx.txt 仍兼容） ================= */
static int cfg_val(const char *key, int def)
{
    static char ini[MAX_PATH];
    static int inited;
    if (!inited) {
        inited = 1;
        lstrcpynA(ini, g_dir, MAX_PATH - 32);
        lstrcatA(ini, "psdto3d_green.ini");
    }
    return GetPrivateProfileIntA("green", key, def, ini);
}

static int cfg_on(const char *key, int def, const char *marker)
{
    if (marker && GetFileAttributesA(marker) != INVALID_FILE_ATTRIBUTES) return 1;   /* 老包兼容 */
    return cfg_val(key, def) != 0;
}
'''

ANCHOR = 'static int writepsd_slot_hooked;'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, HELPER + '\n' + ANCHOR, 1)

# 逐条替换
pat = re.compile(r'GetFileAttributesA\("(_([a-z0-9_]+)\.txt)"\)\s*!=\s*INVALID_FILE_ATTRIBUTES')
pat_eq = re.compile(r'GetFileAttributesA\("(_([a-z0-9_]+)\.txt)"\)\s*==\s*INVALID_FILE_ATTRIBUTES')

def repl(m):
    marker, key = m.group(1), m.group(2)
    d = DEFAULTS.get(key, 0)
    return 'cfg_on("%s", %d, "%s")' % (key, d, marker)

s, n1 = pat.subn(repl, s)
s, n2 = pat_eq.subn(lambda m: '!cfg_on("%s", %d, "%s")' % (m.group(2), DEFAULTS.get(m.group(2), 0), m.group(1)), s)

io.open(P, 'w', encoding='utf-8').write(s)
print('replaced != :%d  ==:%d' % (n1, n2))
