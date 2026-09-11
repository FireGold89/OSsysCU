@echo off
chcp 65001 > nul
title QS管理系統 V2 (5001)
cd /d "%~dp0"

set DATA_DIR=%~dp0_data
set PORT=5001
set DEPLOYMENT_TIER=v2
set PYTHONIOENCODING=utf-8

if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%DATA_DIR%\uploads" mkdir "%DATA_DIR%\uploads"

echo ============================================================
echo   QS管理系統 V2 本機
echo   http://localhost:5001
echo   資料目錄: %DATA_DIR%
echo   如端口被占用，請先關閉其他 python 視窗後重試
echo   按 Ctrl+C 可停止伺服器
echo ============================================================

pip install -r requirements.txt -q 2>nul
start "" "http://localhost:5001"
python app.py
pause
