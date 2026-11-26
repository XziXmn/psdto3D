# -*- coding: utf-8 -*-
"""Rewrite the delivery readme in GBK with the final facts."""
import io
import os

PATH = r'C:\Home\Workspace\UGit\psdto\_work\交付_10.1\说明_交付.txt'

TEXT = """PSDTO3D 10.1 绿色版（去狗 / 仿真狗版）
=====================================

这是什么
--------
原版 psdto3d101.exe + 仿真加密狗 DLL。不用插狗、不用装驱动、不用安装，
整个目录复制到任意位置，双击 psdto3d101.exe 即可。

目录说明
--------
psdto3d101.exe       主程序（含 1 处 2 字节补丁：解除 GIF 导出的按钮闸门）
cmyktiff2.dll        仿真狗（同时负责导出转发）
cmyktiff2_real.dll   原版 TIFF 库（改名保留，仿真狗调用它）
wnaspi32.dll         ASPI 仿真（原程序用它找狗）
其他 dll / sample    原版文件，未改动

已实测可用
----------
1. 启动、狗检测：不插狗直接通过
2. 导入 *.psd
3. 导入工程设置（.tw3d2）
4. 预览：生成完整 ok3dtemp
5. 导出 *.tiff：6,899,708 字节（1969 x 1168）
6. 导出 Gif：约 4.0 MB，11 帧

暂不可用
--------
导出 PSD：会生成约 3 KB 的空壳（11 层、每层 4 通道，但无像素数据）。

原因（已定位到根因链）：
* PSD 的层宽来自中间文件 vwd*.gjs 里的 TIFF 标签 ImageWidth(0x0100)；
* 本版程序把宽度写成了 tag 0x0103、缺 0x0100，于是加载器读到宽度 0，不写像素；
* 该中间文件由哪个模块写出尚未定位（zu06 / cmyktiff2_real / exe 已排除）。

要彻底修好，需要在插着加密狗的真机上跑一次
「启动 -> 导入 PSD -> 导入设置 -> 预览 -> 导出 PSD」并抓一份 _dongle.log。

使用注意
--------
* 工作目录固定为 C:\\ok3dtemp，程序会自己往里写。空间不够会报错。
  该目录不干净时「导入工程设置」可能报 Invalid numeric input，建议每次开跑前清空。
* 导出前必须先「预览」；并且成功导出一次 TIFF 之后，
  「Export PSD / Export Gif」菜单才会变可用（这是原版行为，不是 bug）。
* 杀毒软件可能对 wnaspi32.dll / cmyktiff2.dll 报风险，属误报，可加白名单。

版本信息
--------
主程序 md5 : A8751F844762F0C264538689EFF800D0
仿真狗 md5 : 314408A1DEDBCD6699E44C8784B57FE0
原版库 md5 : 417CE3B6727D839CBD992E910848CD2A
构建时间   : 2026-11-23 夜间
"""

io.open(PATH, 'w', encoding='gbk', errors='replace').write(TEXT)
print('written', os.path.getsize(PATH))
