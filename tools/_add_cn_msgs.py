# -*- coding: utf-8 -*-
"""把几个常见英文提示也汉化：找不到 PSD / 需要简单图层 等。
做法：扫描 exe 映像里的 ASCII 原文，就地写入 GBK（长度不超过原字符串）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'cn_msg_table' in s:
    print('already patched')
    raise SystemExit(0)

# (英文原文, 中文, 目标缓冲长度=原文字节数+1)
ITEMS = [
    ('Can not found the specified psd file!', '找不到指定的 PSD 文件！'),
    ('All layers must be simple layer', '图层必须是普通图层'),
]


def esc(text):
    out = ''
    for b in text.encode('gbk', errors='replace'):
        out += '\\x%02X' % b
    return out


rows = []
for en, cn in ITEMS:
    rows.append('    { "%s", "%s", %d },' % (en, esc(cn), len(en.encode('ascii')) + 1))
TABLE = 'static const struct { const char *en; const char *cn; int maxn; } cn_msg_table[] = {\n' + \
        '\n'.join(rows) + '\n    { 0, 0, 0 }\n};\n'

OLD = '''static void localize_dialogs(void)
{'''
NEW = TABLE + '''
static void localize_dialogs(void)
{
    int mi;'''
assert OLD in s
s = s.replace(OLD, NEW, 1)

# 在函数末尾追加：逐个替换表里的提示
OLD2 = '''    note("cn_dialogs: 没找到 Confirm/continue? 字符串");
}'''
NEW2 = '''    note("cn_dialogs: 没找到 Confirm/continue? 字符串");

    for (mi = 0; cn_msg_table[mi].en; mi++) {
        const char *en = cn_msg_table[mi].en;
        int n = lstrlenA(en);
        unsigned char *q;
        for (q = base; q + n < end; q++) {
            if (memcmp(q, en, n) == 0) {
                patch_bytes(q, cn_msg_table[mi].cn, lstrlenA(cn_msg_table[mi].cn) + 1);
                note("cn_dialogs: %s -> 中文", en);
                break;
            }
        }
    }
}'''
assert OLD2 in s
s = s.replace(OLD2, NEW2, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched ok')
