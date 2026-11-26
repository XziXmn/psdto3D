# -*- coding: utf-8 -*-
"""诊断：找出 TForm1 对象指针（窗口附加字节 / USERDATA），用于调用 TabSheet2Show。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'selfprobe' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
static int selfprobe_done;

static void selfprobe_tick(void)
{
    HWND w = FindWindowA("TForm1", NULL);
    long a, b, c;
    if (!w || selfprobe_done) return;
    a = GetWindowLongA(w, 0);
    b = GetWindowLongA(w, -21);          /* GWL_USERDATA */
    c = GetWindowLongA(w, -16);          /* GWL_HINSTANCE */
    note("selfprobe: win0=%08lX userdata=%08lX hinst=%08lX", (unsigned long)a,
         (unsigned long)b, (unsigned long)c);
    selfprobe_done = 1;
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '''        if (GetFileAttributesA("_tabfix.txt") != INVALID_FILE_ATTRIBUTES)'''
NEW = '''        if (GetFileAttributesA("_selfprobe.txt") != INVALID_FILE_ATTRIBUTES)
            selfprobe_tick();
        if (GetFileAttributesA("_tabfix.txt") != INVALID_FILE_ATTRIBUTES)'''
assert OLD in s, 'loop anchor missing'
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
