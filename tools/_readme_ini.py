# -*- coding: utf-8 -*-
import io

P = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'
t = io.open(P, encoding='gbk').read()

# 1) 开关清单 -> ini
old_switch_start = t.find(' _native_psd.txt       ')
if old_switch_start > 0:
    old_switch_end = t.find('\n', t.find('_inject_x2.txt', old_switch_start))
    # 找到这一段的结束（下一行不是开关）
    lines = t[old_switch_start:].split('\n')
    drop = 0
    for ln in lines:
        if ln.strip().startswith('_') or ln.strip() == '':
            drop += 1
        else:
            break
    old_end = old_switch_start + sum(len(x) + 1 for x in lines[:drop])
    t = t[:old_switch_start] + """ psdto3d_green.ini    配置文件（见下一节），所有功能开关都在里面
 chinese.ini          中文界面开关（存在=中文；删除=英文）
""" + t[old_end:]

# 2) 新增一节说明 ini
anchor = '五、目录里哪些文件是干什么的'
ADD = """五之补充、配置文件 psdto3d_green.ini
---------------------------------
 以前是一堆 "_xxx.txt" 标记文件（存在=开启），现在是同一个 ini：

   [green]
   native_psd=1    导出 PSD 原生写出（0 = 只得到 3 KB 空壳）
   inject_x2=1     导出几何注入（关掉会导致导出异常，建议保持 1）
   gxwj=1          直接打开 99 版工程 .gxwj
   fix_cancel=1    「导入设置」点取消不崩
   layers_up=1     解除 33 层限制（0 = 恢复原版，34 层以上预览会报错）
   psd_limit=0     图层超限时先弹提示再拒绝导入（上限已打通，一般不需要）
   psd_build=0     旧的"导出后补全"流程（新流程不需要）
   cn_ui=0         运行期文字替换汉化（原版自带中文，见 chinese.ini）
   cn_native=0     运行期调用程序自带中文例程（同上）

 改完重开程序生效。旧版的 _xxx.txt 标记文件仍然认（存在即视为开启），
 但新包不再附带，正常使用只需要 ini。

"""
assert anchor in t
t = t.replace(anchor, ADD + anchor, 1)

# 3) 图层那节里的开关描述改掉
t = t.replace(' 开关：_layers_up.txt（存在=启用；删掉=恢复原版 33 层限制）',
              ' 开关：psdto3d_green.ini 里的 layers_up（1=启用；0=恢复原版 33 层限制）')
t = t.replace(" 另：_psd_limit.txt 是“超过 33 层就拦下来提示”的旧保护，",
              " 另：psd_limit 是“超过 33 层就拦下来提示”的旧保护，")
io.open(P, 'w', encoding='gbk', errors='replace').write(t)
print('readme updated, %d chars' % len(t))
