#!/bin/bash
# YouTube 字幕轉換器 - 雙擊啟動

echo "========================================"
echo "🎬 YouTube 字幕轉換器"
echo "========================================"
echo ""

# 進入程式目錄（使用絕對路徑）
APP_DIR="$HOME/ai_class_flywheel/tools/youtube_subtitle_converter"
cd "$APP_DIR"

# 啟動網頁介面
echo "正在啟動..."
echo "請稍候，瀏覽器會自動開啟"
echo ""

# 啟動服務並開啟瀏覽器
python3 web_app.py &
sleep 3
open "http://localhost:7860"

# 保持視窗開啟
echo ""
echo "服務已啟動！"
echo "如果瀏覽器沒有自動開啟，請手動開啟: http://localhost:7860"
echo ""
echo "按 Ctrl+C 可以關閉服務"
wait
