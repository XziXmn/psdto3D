# -*- coding: utf-8 -*-
"""把程序里 "Confirm / continue?" 这类英文对话框改成中文（就地改写 exe 里的字符串）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'localize_dialogs' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 对话框汉化（就地替换 exe 里的英文提示） ================= */
static void patch_bytes(void *dst, const char *src, int n)
{
    DWORD oldp;
    if (!VirtualProtect(dst, n, PAGE_EXECUTE_READWRITE, &oldp)) return;
    memcpy(dst, src, n);
    VirtualProtect(dst, n, oldp, &oldp);
}

static void localize_dialogs(void)
{
    static int done;
    HMODULE he = GetModuleHandleA(0);
    unsigned char *base;
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS *nt;
    unsigned char *p, *end;
    static const char pat[] = "Confirm\0continue?";
    static const char cn_caption[] = "\xC8\xB7\xC8\xCF";                        /* 确认 */
    static const char cn_text[]    = "\xBC\xCC\xD0\xF8\xC2\xF0\xA3\xBF";        /* 继续吗？ */
    if (done || !cfg_val("cn_dialogs", 1)) return;
    done = 1;
    if (!he) return;
    base = (unsigned char *)he;
    dos = (IMAGE_DOS_HEADER *)base;
    nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    end = base + nt->OptionalHeader.SizeOfImage;

    for (p = base; p + sizeof(pat) < end; p++) {
        if (memcmp(p, pat, sizeof(pat)) == 0) {
            patch_bytes(p, cn_caption, sizeof(cn_caption));          /* 覆盖 "Confirm" + NUL */
            patch_bytes(p + 8, cn_text, sizeof(cn_text));            /* 覆盖 "continue?" 前 8 字节 */
            note("cn_dialogs: 已把 Confirm/continue? 改为中文");
            return;
        }
    }
    note("cn_dialogs: 没找到 Confirm/continue? 字符串");
}
'''

ANCHOR = 'static DWORD WINAPI load_watch(LPVOID p)'
assert ANCHOR in s, 'anchor'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

OLD = '        startup_cleanup();'
NEW = '        startup_cleanup();\n        localize_dialogs();'
assert OLD in s
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
