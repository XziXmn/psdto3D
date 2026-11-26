# -*- coding: utf-8 -*-
"""整段重写 psd_guard_dialog，保证字面量引号成对、GBK 转义正确。"""
import io
import re

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

TITLE = '图层数超出程序能力'
BODY = ('这个 PSD 有 %d 个图层。\r\n\r\n'
        '本程序的预览/渲染最多支持 %d 层（第 %d 层开始会崩）。\r\n'
        '请在 Photoshop 里把图层合并到 %d 层以内再导入。\r\n\r\n'
        '（导入本身能接受更多层，但预览会直接报错退出）')


def lit(text, per=20):
    raw = text.encode('gbk', errors='replace')
    toks = []
    for b in raw:
        if b == 0x0D:
            toks.append('\\r')
        elif b == 0x0A:
            toks.append('\\n')
        elif b == 0x22:
            toks.append('\\"')
        elif 32 <= b < 127 and b != 0x5C:
            toks.append(chr(b))
        else:
            toks.append('\\x%02X' % b)
    chunks = [''.join(toks[i:i + per]) for i in range(0, len(toks), per)]
    return '"' + '"\n        "'.join(chunks) + '"'


FUNC = '''static int psd_guard_dialog(const char *path)
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
        %s,
        layers, PSD_MAX_LAYERS, PSD_MAX_LAYERS + 1, PSD_MAX_LAYERS);
    MessageBoxA(0, msg, %s, MB_OK | MB_ICONWARNING);
    return 1;
}''' % (lit(BODY), lit(TITLE))

start = s.find('static int psd_guard_dialog(const char *path)')
end = s.find('\n}', s.find('MessageBoxA(0, msg,', start)) + 2
assert start > 0 and end > start, 'anchor missing'
s = s[:start] + FUNC + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('rewritten function, %d chars' % len(FUNC))
