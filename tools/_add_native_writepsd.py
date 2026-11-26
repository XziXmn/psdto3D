# -*- coding: utf-8 -*-
"""Wire a native writepsd replacement: hook GetProcAddress in the exe."""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'writepsd_shim' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* ================= 原生 writepsd 替换 =================
 * 程序通过 GetProcAddress("writepsd") 拿到 zu06.dll 的导出地址；
 * 我们返回自己的实现，参数沿用 Delphi register 约定：
 *   参数1~3 在 EAX/EDX/ECX，其余在栈上（caller 清栈）。
 */
static void *g_writepsd_c;

static int __cdecl writepsd_c(const char *file, const char *dir, void *p3,
                              int a4, int a5, int a6, int a7,
                              int layers, int w, int h, int spp, int a12, int a13)
{
    (void)p3; (void)a4; (void)a5; (void)a6; (void)a7; (void)spp; (void)a12; (void)a13;
    note("NATIVE writepsd: file=%s dir=%s layers=%d w=%d h=%d", file ? file : "(null)",
         dir ? dir : "(null)", layers, w, h);
    if (!file || !dir) return 0;
    if (layers <= 0 || layers > 64 || w <= 0 || h <= 0) {
        note("NATIVE writepsd: 参数不合理，交给原实现");
        return -1;
    }
    psd_assemble(file, dir, w, h, layers);
    return 0;
}

__attribute__((naked)) static void writepsd_shim(void)
{
    __asm__ __volatile__(
        "pushl %ecx\n\t"
        "pushl %edx\n\t"
        "pushl %eax\n\t"
        "movl g_writepsd_c, %eax\n\t"
        "call *%eax\n\t"
        "addl $12, %esp\n\t"
        "ret\n\t");
}

static void * WINAPI e_gpa(HMODULE mod, LPCSTR name)
{
    void *r = o_gpa ? o_gpa(mod, name) : 0;
    if (name && lstrcmpiA(name, "writepsd") == 0) {
        if (GetFileAttributesA("_native_psd.txt") != INVALID_FILE_ATTRIBUTES) {
            g_writepsd_c = (void *)writepsd_c;
            note("NATIVE writepsd: 拦截成功，返回本地实现 %p", (void *)writepsd_shim);
            return (void *)writepsd_shim;
        }
    }
    return r;
}
'''

ANCHOR = 'static BOOL WINAPI e_gsfn(void *p)'
assert ANCHOR in s, 'anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
