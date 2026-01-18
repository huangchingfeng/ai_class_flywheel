#!/bin/bash
# YouTube 字幕轉換器 - 啟動腳本

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

# 進入程式目錄
cd "$HOME/ai_class_flywheel/tools/youtube_subtitle_converter"

# 關閉舊服務
lsof -ti:7860 | xargs kill -9 2>/dev/null

# 清理快取
rm -rf __pycache__ .gradio 2>/dev/null

echo "  🚀 正在啟動服務..."
echo ""

# 啟動服務
python3 web_app.py &
PID=$!

# 等待服務啟動
sleep 4

# 開啟瀏覽器
open "http://localhost:7860"

echo "  ✅ 服務已啟動！"
echo ""
echo "  📍 本機網址: http://localhost:7860"
echo ""
echo "  💡 提示: 關閉此視窗即可停止服務"
echo ""

# 等待服務結束
wait $PID
