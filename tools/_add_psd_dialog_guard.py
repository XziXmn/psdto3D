# -*- coding: utf-8 -*-
"""在打开文件对话框返回时检查 PSD 层数：超过程序实际能力就明确提示并取消，避免崩溃。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'psd_guard_dialog' in s:
    print('already patched')
    raise SystemExit(0)

BLOCK = r'''
/* 程序实际能力：预览/渲染最多 33 层（第 34 层起会读一个从未分配的数组） */
#define PSD_MAX_LAYERS 33

static int psd_guard_dialog(const char *path)
{
    char msg[700];
    int layers = 0, ch = 0, mode = 0;
    HANDLE fh;
    unsigned char head[26];
    DWORD got = 0;
    if (!path) return 0;
    {
        int l = lstrlenA(path);
        if (l < 5 || lstrcmpiA(path + l - 4, ".psd") != 0) return 0;
    }
    if (GetFileAttributesA("_psd_limit.txt") == INVALID_FILE_ATTRIBUTES) return 0;
    fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (fh == INVALID_HANDLE_VALUE) return 0;
    if (!ReadFile(fh, head, 26, &got, 0) || got != 26 || memcmp(head, "8BPS", 4) != 0) {
        CloseHandle(fh);
        return 0;
    }
    ch = (head[12] << 8) | head[13];
    mode = (head[24] << 8) | head[25];
    {
        DWORD d = 0; long n;
        ReadFile(fh, &d, 4, &got, 0);
        n = (long)(((d) & 0xFF) << 24 | (((d) >> 8) & 0xFF) << 16 | (((d) >> 16) & 0xFF) << 8 | ((d) >> 24 & 0xFF));
        SetFilePointer(fh, n, 0, FILE_CURRENT);
        ReadFile(fh, &d, 4, &got, 0);
        n = (long)(((d) & 0xFF) << 24 | (((d) >> 8) & 0xFF) << 16 | (((d) >> 16) & 0xFF) << 8 | ((d) >> 24 & 0xFF));
        SetFilePointer(fh, n, 0, FILE_CURRENT);
    }
    { unsigned char z[8]; ReadFile(fh, z, 8, &got, 0); }
    { unsigned char c[2] = {0,0}; ReadFile(fh, c, 2, &got, 0);
      layers = (short)((c[0] << 8) | c[1]); if (layers < 0) layers = -layers; }
    CloseHandle(fh);
    note("PSD guard: %s 层=%d 通道=%d 模式=%d", path, layers, ch, mode);
    if (layers <= PSD_MAX_LAYERS) return 0;
    wsprintfA(msg,
        "这个 PSD 有 %d 个图层。\r\n\r\n"
        "本程序的预览/渲染最多支持 %d 层（第 %d 层开始会崩）。\r\n"
        "请在 Photoshop 里把图层合并到 %d 层以内再导入。\r\n\r\n"
        "（导入本身能接受更多层，但预览会直接报错退出）",
        layers, PSD_MAX_LAYERS, PSD_MAX_LAYERS + 1, PSD_MAX_LAYERS);
    MessageBoxA(0, msg, "图层数超出程序能力", MB_OK | MB_ICONWARNING);
    return 1;
}
'''

ANCHOR = 'static BOOL WINAPI e_gofna(void *p)'
if ANCHOR not in s:
    ANCHOR = 'static BOOL WINAPI e_gofna(LPVOID p)'
assert ANCHOR in s, 'gofna anchor missing'
s = s.replace(ANCHOR, BLOCK + '\n' + ANCHOR, 1)

# 在 e_gofna 返回 TRUE 之前做检查（队列分支）
OLD = '''        if (file && maxfile) lstrcpynA(file, g_saves[g_isave], maxfile);'''
NEW = OLD   # 保存对话框，跳过
OLD2 = '''        if (file && maxfile) lstrcpynA(file, g_opens[g_iopen], maxfile);'''
NEW2 = '''        if (file && maxfile) lstrcpynA(file, g_opens[g_iopen], maxfile);
        if (psd_guard_dialog(g_opens[g_iopen])) {
            g_iopen++;
            if (g_iopen >= g_nopen) g_iopen = g_nopen - 1;
            return FALSE;
        }'''
if OLD2 in s:
    s = s.replace(OLD2, NEW2, 1)

io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok (queue branch only)' if OLD2 in s else 'patched but queue anchor missing')
