# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'PSD count debug' in s:
    print('already there')
    raise SystemExit(0)

OLD = '''      *layers = cnt; }
    CloseHandle(fh);
    return 1;'''
NEW = '''      *layers = cnt; }
    note("PSD count debug: %s -> layers=%d", path, *layers);
    CloseHandle(fh);
    return 1;'''
assert OLD in s, 'anchor missing'
s = s.replace(OLD, NEW, 1)

OLD2 = '''    if (!ReadFile(fh, head, 26, &got, 0) || got != 26 || memcmp(head, "8BPS", 4) != 0) {
        CloseHandle(fh);
        return 0;
    }'''
NEW2 = '''    if (!ReadFile(fh, head, 26, &got, 0) || got != 26 || memcmp(head, "8BPS", 4) != 0) {
        note("PSD count debug: %s 头部读取失败 (got=%lu)", path, (unsigned long)got);
        CloseHandle(fh);
        return 0;
    }'''
assert OLD2 in s, 'anchor2 missing'
s = s.replace(OLD2, NEW2, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched')
