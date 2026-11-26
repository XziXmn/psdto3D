"""Write the per-package launcher + readme for a psdto3d 绿色版 folder."""
import os
import sys

PKG = {
    'psdto3d2022绿色版': {
        'version': 'PSDTO3D Version 2022 (for windows 10)',
        'exe_date': '2025-03-24 07:52:06',
        'src': 'Psdto3d\\',
        'sha_src': '9521816A4294DCC53AD52DB0033137BB1E2730CEDBAD4309B61D36EFE9609570',
        'sha_out': '26be32d55564c911ddf8e9c328f616afd6f62f23b871f044967de798d8ad66bf',
        'offsets': '文件偏移 0x102419（VA 0x503019，75 0F→EB 0F）、0x10242F（VA 0x50302F，85 C0→31 C0）',
        'about_png': '关于_2022版本.png',
    },
    'psdto3d10.1绿色版': {
        'version': 'PSDTO3D Version 10.1',
        'exe_date': '2020-09-30 15:34:20',
        'src': 'Psdto3d (2)\\',
        'sha_src': 'B3CB72B4AA3DD2CE878AC738438707F0F53D0F70B8EA29CECCD57AF69D545E8D',
        'sha_out': '442794870dfb3fb5c9d78b9e1ec5ecee87abf0c5d82f00d2c57983d5c821d8f7',
        'offsets': '文件偏移 0x10242E（VA 0x50302E，75 0F→EB 0F）、0x102444（VA 0x503044，85 C0→31 C0）',
        'about_png': '关于_10.1版本.png',
    },
}

LAUNCHER = r'''@echo off
rem Portable launcher: keeps the working directory on the package folder so the
rem settings file (psdto3d104.inf) stays portable.
setlocal
cd /d "%~dp0"
start "" "%~dp0psdto3d101.exe" %*
endlocal
'''

README = '''{name}  ——  PSDTO3D 绿色版（免安装 / 免加密狗 / 免管理员）
================================================================

版本        ：{version}
原始程序    ：{src}psdto3d101.exe（构建日期 {exe_date}）
原始 SHA256 ：{sha_src}
绿色版 SHA256：{sha_out}

一、启动
    双击「启动 psdto3d101.cmd」，或直接双击 psdto3d101.exe。
    首次关闭程序后，会在本目录生成/更新设置文件 psdto3d104.inf。

二、这个包做了什么
    1. 免加密狗：程序启动时会查询 USBKey 软件锁（返回值 0xFFFFFBE3 = 未找到），
       找不到就弹 "The system did not find any software key, please insert it."
       然后退出。绿色版把该判断的两个分支改成"始终走已授权继续"，
       不再要求加密狗，也不再弹注册文件错误。
       修改位置：{offsets}
    2. 免管理员：原 exe 内嵌清单要求 requireAdministrator（每次启动都弹 UAC）。
       绿色版把清单改成 asInvoker，普通用户双击即可运行。
    3. 64 位兼容：原 exe 未设置 IMAGE_FILE_LARGE_ADDRESS_AWARE，在 64 位 Windows
       上作为 32 位进程只能用到 2GB 地址空间，大 PSD 容易"内存不足"。
       绿色版已置该标志（Characteristics 0x818E → 0x81AE），
       在 x64 系统上同一进程可用满 4GB 用户地址空间，可直接处理更大的 PSD。
       程序本身仍是 32 位（源码不可得，无法生成原生 x64 版本）。
    4. 免安装 / 不写注册表：程序只读取 Borland RTL 的语言设置项，
       不写产品注册表；设置写在同目录 psdto3d104.inf；无需安装、无需注册服务。
    5. 修正 PE 校验和，便于完整性校验与部分杀软放行。

三、目录说明
    psdto3d101.exe        已修改的主程序
    psdto3d101.exe.orig   原始未修改的主程序（回滚用：改名覆盖即可）
    psdto3d104.inf        设置文件（LPI / 角度 / DPI / 尺寸等）
    sample\\              官方示例 PSD 与工程文件
    其余 DLL              PSD 读写（zu06/dspr）、TIFF 合成（cmyktiff2）、
                          CMYK、GIF/MOV 等运行库，均保持原样

四、注意事项
    * 程序会在系统盘根目录创建临时目录 %SystemDrive%\\ok3dtemp\\ 存放中间 TIFF，
      这是程序内写死的路径，用完可手动清空；若系统盘根目录不允许建目录，
      请把程序放在有写权限的位置并手动创建该目录。
    * 程序使用 ANSI 文件 API，路径尽量不超过 260 字符；PSD 与输出目录不要放太深。
    * 32 位进程 + 4GB 上限：超大 PSD（解压后 >4GB）仍会受限，建议先用 Photoshop
      拼合/降低分辨率后再导入。
    * 绿色版不再调用 KeyReg101.exe；注册相关菜单项无实际作用。

五、自检
    python ..\\tools\\verify_green.py --dir . --launch
    全部 PASS 表示：x86 映像、4GB 标志、两处授权补丁、asInvoker 清单、
    设置文件就位、启动无弹框。
'''


def main(root):
    for name, meta in PKG.items():
        d = os.path.join(root, name)
        if not os.path.isdir(d):
            print('missing', d)
            continue
        with open(os.path.join(d, '启动 psdto3d101.cmd'), 'w', encoding='gbk', newline='\r\n') as f:
            f.write(LAUNCHER)
        with open(os.path.join(d, '绿色版说明.txt'), 'w', encoding='utf-8-sig', newline='\r\n') as f:
            f.write(README.format(name=name, **meta))
        print('written', name)


if __name__ == '__main__':
    main(sys.argv[1])

