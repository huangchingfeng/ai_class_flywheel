#!/bin/bash
# YouTube 字幕轉換器 - 啟動腳本

echo "========================================"
echo "🎬 YouTube 字幕轉換器"
echo "========================================"
echo ""

# 取得腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 檢查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 找不到 Python3，請先安裝 Python"
    exit 1
fi

# 檢查依賴
echo "檢查依賴套件..."
pip3 install -q gradio google-generativeai yt-dlp 2>/dev/null

# 啟動應用程式
echo ""
echo "正在啟動網頁介面..."
echo "請在瀏覽器開啟: http://localhost:7860"
echo ""
echo "按 Ctrl+C 可以關閉程式"
echo ""

python3 web_app.py
