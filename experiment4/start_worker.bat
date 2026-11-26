@echo off
chcp 65001 >nul
rem Optional Celery worker; needs Redis on localhost:6379
cd /d "%~dp0backend"
python -m celery -A app.celery_app worker --pool=solo -l info
pause
