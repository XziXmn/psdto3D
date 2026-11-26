@echo off
chcp 936 >nul
rem 用法: 转换99工程.cmd "输入.gxwj" "输出.tw3d2" "工程指向的psd"
if "%~3"=="" (
  echo 用法: 拖入或用命令行: 转换99工程.cmd 输入.gxwj 输出.tw3d2 目标.psd
  pause
  exit /b 1
)
python "%~dp0gxwj2tw3d2.py" "%~1" "%~2" --psd "%~3"
pause