/* 文件对话框接管：按顺序把 _dlgopen.txt / _dlgsave.txt 里的路径喂给程序。
 *
 * 为什么在 DLL 里做而不是在启动器里：启动器的桩只能返回一个固定路径，
 * "导入 PSD" 和 "打开工程" 会拿到同一个文件，流程就走歪了。
 * 这里按调用次数依次取，第 N 次打开对话框拿第 N 行。
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef BOOL (WINAPI *PF_OpenFile)(LPOPENFILENAMEA);
typedef BOOL (WINAPI *PF_SaveFile)(LPOPENFILENAMEA);

static PF_OpenFile g_o_open;
static PF_SaveFile g_o_save;
static char g_dlg_dir[MAX_PATH];
static int g_open_idx, g_save_idx;

extern void dlg_note(const char *fmt, ...);

static int load_list(const char *name, char out[][MAX_PATH], int maxn)
{
    char p[MAX_PATH];
    FILE *f;
    int n = 0;
    lstrcpyA(p, g_dlg_dir);
    lstrcatA(p, name);
    f = fopen(p, "rb");
    if (!f) return 0;
    while (n < maxn && fgets(p, MAX_PATH, f)) {
        char *s = p;
        size_t L;
        while (*s == ' ' || *s == '\t') s++;
        L = strlen(s);
        while (L && (s[L - 1] == '\n' || s[L - 1] == '\r' || s[L - 1] == ' ')) s[--L] = 0;
        if (!L || s[0] == '#') continue;
        lstrcpynA(out[n], s, MAX_PATH);
        n++;
    }
    fclose(f);
    return n;
}

static void fill_ofn(LPOPENFILENAMEA o, const char *path)
{
    int i, L;
    if (!o || !o->lpstrFile || !o->nMaxFile) return;
    lstrcpynA(o->lpstrFile, path, (int)o->nMaxFile);
    /* nFileOffset = 文件名在路径里的下标；nFileExtension = 扩展名起点 */
    L = lstrlenA(o->lpstrFile);
    o->nFileOffset = 0;
    for (i = 0; i < L; i++) if (o->lpstrFile[i] == '\\' || o->lpstrFile[i] == '/') o->nFileOffset = i + 1;
    o->nFileExtension = 0;
    for (i = o->nFileOffset; i < L; i++)
        if (o->lpstrFile[i] == '.') { o->nFileExtension = i + 1; break; }
    if (o->lpstrFileTitle && o->nMaxFileTitle) {
        lstrcpynA(o->lpstrFileTitle, o->lpstrFile + o->nFileOffset, (int)o->nMaxFileTitle);
    }
}

static void log_ofn(const char *tag, LPOPENFILENAMEA o)
{
    if (!o) { dlg_note("%s: ofn=NULL", tag); return; }
    {
        char flt[200];
        int k = 0;
        const char *f = o->lpstrFilter;
        flt[0] = 0;
        if (f) {
            /* lpstrFilter 是 "描述\0*.ext\0...\0\0" 的成对列表 */
            while (*f && k < 180) {
                const char *s = f;
                while (*s && k < 180) flt[k++] = *s++;
                flt[k++] = ' ';
                f = s + 1;
            }
            flt[k] = 0;
        }
        dlg_note("%s: hwnd=%p flags=0x%X filteridx=%u filter=[%s] defext=%s",
                 tag, o->hwndOwner, o->Flags, o->nFilterIndex, flt,
                 o->lpstrDefExt ? o->lpstrDefExt : "");
    }
}

BOOL WINAPI h_dlg_open(LPOPENFILENAMEA o)
{
    static char list[16][MAX_PATH];
    static int n = -1;
    if (n < 0) {
        n = load_list("_dlgopen.txt", list, 16);
        dlg_note("open 列表 %d 条", n);
    }
    log_ofn("OPEN-req", o);
    if (n <= 0) return g_o_open ? g_o_open(o) : FALSE;
    if (g_open_idx >= n) g_open_idx = n - 1;
    dlg_note("OPEN 对话框 #%d -> %s", g_open_idx, list[g_open_idx]);
    fill_ofn(o, list[g_open_idx]);
    g_open_idx++;
    return TRUE;
}

BOOL WINAPI h_dlg_save(LPOPENFILENAMEA o)
{
    static char list[16][MAX_PATH];
    static int n = -1;
    if (n < 0) {
        n = load_list("_dlgsave.txt", list, 16);
        dlg_note("save 列表 %d 条", n);
    }
    log_ofn("SAVE-req", o);
    if (n <= 0) return g_o_save ? g_o_save(o) : FALSE;
    if (g_save_idx >= n) g_save_idx = n - 1;
    dlg_note("SAVE 对话框 #%d -> %s", g_save_idx, list[g_save_idx]);
    fill_ofn(o, list[g_save_idx]);
    g_save_idx++;
    return TRUE;
}

void dlg_stub_start(const char *exe_dir, void *real_open, void *real_save)
{
    lstrcpynA(g_dlg_dir, exe_dir, MAX_PATH);
    g_o_open = (PF_OpenFile)real_open;
    g_o_save = (PF_SaveFile)real_save;
}
