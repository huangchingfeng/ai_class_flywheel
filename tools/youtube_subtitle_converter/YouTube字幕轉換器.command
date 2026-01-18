#!/bin/bash
# YouTube 字幕轉換器 - 雙擊啟動

clear
echo ""
echo "  ╔═══════════════════════════════════════════════════════╗"
echo "  ║                                                       ║"
echo "  ║   ▶ YouTube  字幕轉換器                               ║"
echo "  ║                                                       ║"
echo "  ║   AI 智慧翻譯 · 多語言支援 · 一鍵產生字幕             ║"
echo "  ║                                                       ║"
echo "  ╚═══════════════════════════════════════════════════════╝"
echo ""

# 進入程式目錄（使用絕對路徑）
APP_DIR="$HOME/ai_class_flywheel/tools/youtube_subtitle_converter"
cd "$APP_DIR"

# 關閉舊的服務（如果有的話）
lsof -ti:7860 | xargs kill -9 2>/dev/null

# 清理快取
rm -rf __pycache__ .gradio 2>/dev/null

echo "  🚀 正在啟動服務..."
echo ""

# 啟動服務並開啟瀏覽器
python3 web_app.py &
sleep 4
open "http://localhost:7860"

echo ""
echo "  ✅ 服務已啟動！"
echo ""
echo "  📍 本機網址: http://localhost:7860"
echo ""
echo "  💡 提示: 按 Ctrl+C 可以關閉服務"
echo ""
echo "  ─────────────────────────────────────────────────────────"
echo ""
wait
