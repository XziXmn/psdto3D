# -*- coding: utf-8 -*-
"""加 cap_io 模式：只对设备 I/O 透传+记录，对话框/工程转换照常走我们的逻辑。
开关：_capio.txt 存在即生效。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cap_io' in s:
    print('already patched')
    raise SystemExit(0)

# 1) 新函数
OLD = '''static int capture_mode(void)
{'''
NEW = '''static int cap_io(void)
{
    static int v = -1;
    if (v < 0) {
        char cp[MAX_PATH];
        lstrcpyA(cp, g_dir);
        lstrcatA(cp, "_capio.txt");
        v = (GetFileAttributesA(cp) != INVALID_FILE_ATTRIBUTES) ? 1 : 0;
        note("EMU cap_io mode = %d", v);
    }
    return v;
}

static int capture_mode(void)
{'''
assert OLD in s
s = s.replace(OLD, NEW, 1)

# 2) e_dio / e_rf / e_wf 的判断改成 cap_io()（设备 I/O 才透传）
import re
count = 0
for fn in ('e_dio', 'e_rf', 'e_wf'):
    i = s.find('static BOOL WINAPI %s(' % fn)
    if i < 0:
        continue
    j = s.find('capture_mode()', i)
    k = s.find('static ', i + 10)
    if 0 <= j < (k if k > 0 else len(s)):
        s = s[:j] + 'cap_io()' + s[j + len('capture_mode()'):]
        count += 1

# 3) e_cfa 也要透传（打开设备句柄）
i = s.find('static HANDLE WINAPI e_cfa(LPCSTR name')
j = s.find('capture_mode()', i)
k = s.find('static ', i + 10)
if 0 <= j < (k if k > 0 else len(s)):
    s = s[:j] + 'cap_io()' + s[j + len('capture_mode()'):]
    count += 1

io.open(P, 'w', encoding='utf-8').write(s)
print('patched, %d 处改成 cap_io()' % count)
