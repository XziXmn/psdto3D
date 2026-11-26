# -*- coding: utf-8 -*-
"""修正上一步：按"完整转义单元"切分字符串字面量，避免把 \\xNN 拆断。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()

TITLE = '图层数超出程序能力'
BODY = ('这个 PSD 有 %d 个图层。\r\n\r\n'
        '本程序的预览/渲染最多支持 %d 层（第 %d 层开始会崩）。\r\n'
        '请在 Photoshop 里把图层合并到 %d 层以内再导入。\r\n\r\n'
        '（导入本身能接受更多层，但预览会直接报错退出）')


def c_literal(text, per=24):
    raw = text.encode('gbk', errors='replace')
    toks = []
    for b in raw:
        if 32 <= b < 127 and b not in (0x22, 0x5C):
            toks.append(chr(b))
        elif b == 0x0D:
            toks.append('\\r')
        elif b == 0x0A:
            toks.append('\\n')
        elif b == 0x22:
            toks.append('\\"')
        else:
            toks.append('\\x%02X' % b)
    # 按 token 数分块，块之间用 " 换行 " 连接
    chunks = [''.join(toks[i:i + per]) for i in range(0, len(toks), per)]
    return '"\n        "'.join(chunks)


NEW = ('    wsprintfA(msg,\n        %s,\n        layers, PSD_MAX_LAYERS, PSD_MAX_LAYERS + 1, PSD_MAX_LAYERS);\n'
       '    MessageBoxA(0, msg, %s, MB_OK | MB_ICONWARNING);') % ('"'+c_literal(BODY)[1:], '"'+c_literal(TITLE)+'"')

start = s.find('    wsprintfA(msg,')
end = s.find('MB_OK | MB_ICONWARNING);', start)
assert start > 0 and end > start
end += len('MB_OK | MB_ICONWARNING);')
s = s[:start] + NEW + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('rewritten')
