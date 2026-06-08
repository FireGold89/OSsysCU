@echo off
chcp 65001 > nul
title QS付款管理系統
echo ============================================================
echo   QS付款管理系統 v1.0
echo   正在啟動...
echo   如端口被占用，请先关闭其他 python 窗口后重试
echo ============================================================
cd /d "%~dp0"
if not exist uploads mkdir uploads
pip install -r requirements.txt -q 2>nul
start "" "http://localhost:5000"
python app.py
pause
