@echo off
chcp 936 >nul
echo 正在清理 PSDTO3D 渲染临时缓存目录 (%SystemDrive%\ok3dtemp)...
echo 注意：该操作仅清理光栅分层切片中间缓存，不影响已导出的成品文件。
set /p ans=确认清理吗？(Y/N): 
if /i not "%ans%"=="Y" goto :eof
del /q "%SystemDrive%\ok3dtemp\*.*" 2>nul
for /d %%d in ("%SystemDrive%\ok3dtemp\*") do rd /s /q "%%d" 2>nul
del /q "%~dp0_dongle.log" 2>nul
echo [OK] 临时缓存与切片文件已成功清理完成！
pause
