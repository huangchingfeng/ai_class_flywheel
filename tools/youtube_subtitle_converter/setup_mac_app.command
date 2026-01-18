#!/bin/bash
# YouTube 字幕轉換器 - Mac 應用程式設置
# 雙擊此檔案來設置桌面應用程式

clear
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║                                                       ║"
echo "║   🎬 YouTube 字幕轉換器 - Mac 應用程式設置            ║"
echo "║                                                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# 獲取腳本所在目錄
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_NAME="YouTube字幕轉換器.app"
APP_PATH="$SCRIPT_DIR/$APP_NAME"
DESKTOP_PATH="$HOME/Desktop/$APP_NAME"

echo "📁 應用程式路徑: $APP_PATH"
echo ""

# 檢查應用程式是否存在
if [ ! -d "$APP_PATH" ]; then
    echo "❌ 找不到應用程式：$APP_PATH"
    exit 1
fi

# 創建圖標
echo "🎨 正在創建圖標..."
echo ""

# 使用 Python 創建圖標
python3 "$SCRIPT_DIR/setup_mac_icon.py" << EOF
n
EOF

# 複製到桌面
echo ""
echo "📋 正在複製應用程式到桌面..."

if [ -d "$DESKTOP_PATH" ]; then
    rm -rf "$DESKTOP_PATH"
fi

cp -R "$APP_PATH" "$DESKTOP_PATH"

if [ -d "$DESKTOP_PATH" ]; then
    echo "✅ 應用程式已複製到桌面！"
    echo ""
    echo "📍 位置: $DESKTOP_PATH"
    echo ""

    # 刪除舊的 .command 檔案（如果在桌面上有的話）
    OLD_COMMAND="$HOME/Desktop/YouTube字幕轉換器.command"
    if [ -f "$OLD_COMMAND" ]; then
        echo "🗑️  正在移除舊的啟動檔案..."
        rm -f "$OLD_COMMAND"
        echo "✅ 已移除舊檔案"
        echo ""
    fi

    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║                                                       ║"
    echo "║   ✅ 設置完成！                                       ║"
    echo "║                                                       ║"
    echo "║   現在您可以從桌面雙擊「YouTube字幕轉換器」啟動       ║"
    echo "║                                                       ║"
    echo "╚═══════════════════════════════════════════════════════╝"
else
    echo "❌ 複製失敗"
fi

echo ""
echo "按任意鍵關閉此視窗..."
read -n 1
