@echo off
chcp 65001 >nul
rem EcoSort backend (activate your conda env first)
cd /d "%~dp0backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
