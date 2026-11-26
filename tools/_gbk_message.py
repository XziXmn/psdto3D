# -*- coding: utf-8 -*-
"""把守卫提示文本改成 GBK 字节转义（源码是 UTF-8，直接写 MessageBoxA 会乱码）。"""
import io
import re

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

TITLE = '图层数超出程序能力'
BODY = ('这个 PSD 有 %d 个图层。\r\n\r\n'
        '本程序的预览/渲染最多支持 %d 层（第 %d 层开始会崩）。\r\n'
        '请在 Photoshop 里把图层合并到 %d 层以内再导入。\r\n\r\n'
        '（导入本身能接受更多层，但预览会直接报错退出）')


def c_literal(text):
    raw = text.encode('gbk', errors='replace')
    out = []
    for b in raw:
        if b == 0x22:
            out.append('\\"')
        elif b == 0x5C:
            out.append('\\\\')
        elif 32 <= b < 127:
            out.append(chr(b))
        else:
            out.append('\\x%02X' % b)
    lit = ''.join(out)
    # 避免 \x 后紧跟十六进制字符导致歧义：切分成多个字符串字面量
    parts = re.findall(r'.{1,40}', lit)
    return '"\n        "'.join(parts)


NEW_WS = ('    wsprintfA(msg,\n        "%s",\n        layers, PSD_MAX_LAYERS, PSD_MAX_LAYERS + 1, PSD_MAX_LAYERS);\n'
          '    MessageBoxA(0, msg, "%s", MB_OK | MB_ICONWARNING);') % (c_literal(BODY), c_literal(TITLE))

start = s.find('    wsprintfA(msg,\n        "这个 PSD')
end = s.find('MB_OK | MB_ICONWARNING);', start)
if start < 0 or end < 0:
    print('anchor not found', start, end)
    raise SystemExit(1)
end += len('MB_OK | MB_ICONWARNING);')
s = s[:start] + NEW_WS + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('rewritten message with GBK escapes')
