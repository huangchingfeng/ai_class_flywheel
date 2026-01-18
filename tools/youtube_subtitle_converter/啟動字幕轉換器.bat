@echo off
chcp 65001 >nul
title YouTube 字幕轉換器

echo ========================================
echo 🎬 YouTube 字幕轉換器
echo ========================================
echo.

cd /d "%~dp0"

:: 檢查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 找不到 Python，請先安裝 Python
    pause
    exit /b 1
)

:: 安裝依賴
echo 檢查依賴套件...
pip install -q gradio google-generativeai yt-dlp 2>nul

echo.
echo 正在啟動網頁介面...
echo 請在瀏覽器開啟: http://localhost:7860
echo.
echo 按 Ctrl+C 可以關閉程式
echo.

python web_app.py

pause
