@echo off
title EcoSort 一键启动

rem ============================================================
rem 启动：实验4后端(8000，含页面与Agent代理) + Agent服务(8001)
rem 前提：使用本机 mypy 环境（需安装项目依赖）
rem ============================================================
cd /d "%~dp0"

if not exist "D:\Anaconda\envs\mypy\python.exe" (
    echo [错误] 未找到 mypy 解释器：D:\Anaconda\envs\mypy\python.exe
    pause & exit /b 1
)

set ECOSORT_PT=%~dp0experiment2\weights\best_5class_v4.pt
set ECOSORT_ONNX=%~dp0experiment2\weights\best_5class_v4.onnx
set ECOSORT_ROOT=%~dp0

echo [1/2] 启动 Agent 服务（8001，DeepSeek 大脑）...
start "EcoSort-Agent-8001" cmd /k "cd /d %~dp0experiment5 && D:\Anaconda\envs\mypy\python.exe -m uvicorn agent_api:app --host 127.0.0.1 --port 8001"

echo [2/2] 启动后端（8000，页面+检测/文本API+Agent代理，模型加载约40秒）...
start "EcoSort-Backend-8000" cmd /k "cd /d %~dp0experiment4\backend && D:\Anaconda\envs\mypy\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo 等待服务就绪（45 秒）...
timeout /t 45 /nobreak >nul
start "" "http://localhost:8000/?launch=%RANDOM%%RANDOM%#/agent"

echo.
echo 两个服务在独立窗口运行，关闭对应窗口即停止该服务；
echo 或双击「一键停止.bat」。
pause
