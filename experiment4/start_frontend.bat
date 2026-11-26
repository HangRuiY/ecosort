@echo off
chcp 65001 >nul
rem EcoSort frontend dev server (Node.js 24)
cd /d "%~dp0frontend"
if not exist node_modules call npm install
call npm run dev
pause
