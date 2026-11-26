@echo off
title EcoSort 一键停止

rem 按端口结束进程：8000=后端页面，8001=Agent服务
for %%P in (8000 8001) do (
    echo 停止端口 %%P ...
    powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %%P -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { taskkill /F /PID $_ }" >nul 2>&1
)
echo 完成。
pause
