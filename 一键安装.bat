@echo off
title EcoSort 一键安装（首次运行，需联网约10分钟）

rem ============================================================
rem 环境自适应：自动寻找 Python 3.10+，在本目录创建 venv 并装依赖
rem 不需要 conda、不需要 Node.js（前端已预编译）
rem ============================================================
cd /d "%~dp0"

set PY=
where py >nul 2>nul && py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set PY=python

if not defined PY (
    echo [错误] 未找到 Python 3.10+。请安装 Python 3.12：
    echo        https://www.python.org/downloads/  安装时勾选 Add to PATH
    pause & exit /b 1
)
echo 使用解释器: %PY%

if exist venv\Scripts\python.exe (
    echo venv 已存在，跳过创建。如需重装请删除 venv 文件夹后重新运行。
) else (
    %PY% -m venv venv || (echo [错误] venv 创建失败 & pause & exit /b 1)
)

echo 升级 pip 并安装依赖（清华/腾讯镜像，约10分钟）...
venv\Scripts\python.exe -m pip install -q --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
venv\Scripts\pip.exe install -q -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络后重试，或把 requirements.txt 中
    echo        的镜像地址换成可访问的源。
    pause & exit /b 1
)

echo.
echo [OK] 安装完成！双击「一键启动.bat」即可运行系统。
pause
