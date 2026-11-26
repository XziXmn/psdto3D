# -*- coding: utf-8 -*-
"""加总开关 exe_patches（默认 1）：设为 0 时不安装任何针对 10.1 的 exe 补丁，
这样同一个 DLL 也能挂到 2022 版上（只提供狗仿真 + 对话框队列）。"""
import io

P = r'C:\Home\Workspace\UGit\psdto\cmykdrop\dongle_emu.c'
s = io.open(P, encoding='utf-8', errors='replace').read()
if 'exe_patches' in s:
    print('already patched')
    raise SystemExit(0)

OLD = '''static void sbp_arm(unsigned long va)
{
    unsigned char *pp = (unsigned char *)va;
    DWORD old;
    if (g_nsbp >= 24) return;'''
NEW = '''static void sbp_arm(unsigned long va)
{
    unsigned char *pp = (unsigned char *)va;
    DWORD old;
    if (!cfg_val("exe_patches", 1)) return;      /* exe_patches: 0 = 不动目标 exe */
    if (g_nsbp >= 24) return;'''
assert OLD in s
s = s.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('patched sbp_arm')
