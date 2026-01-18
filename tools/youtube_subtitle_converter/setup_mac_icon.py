#!/usr/bin/env python3
"""
Mac 應用程式圖標設置腳本
在 Mac 上執行此腳本來生成 YouTube 字幕轉換器的圖標
"""

import subprocess
import os
from pathlib import Path

def create_youtube_icon():
    """創建 YouTube 風格的圖標"""

    # 獲取腳本所在目錄
    script_dir = Path(__file__).parent
    app_path = script_dir / "YouTube字幕轉換器.app" / "Contents" / "Resources"

    # 確保目錄存在
    app_path.mkdir(parents=True, exist_ok=True)

    # 創建圖標集目錄
    iconset_path = app_path / "AppIcon.iconset"
    iconset_path.mkdir(exist_ok=True)

    # 使用 Python 創建簡單的 PNG 圖標
    try:
        from PIL import Image, ImageDraw

        def create_icon(size):
            """創建指定尺寸的 YouTube 風格圖標"""
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 繪製紅色圓角矩形背景
            margin = int(size * 0.1)
            radius = int(size * 0.15)

            # 繪製背景
            draw.rounded_rectangle(
                [margin, margin, size - margin, size - margin],
                radius=radius,
                fill=(255, 0, 0, 255)
            )

            # 繪製白色播放按鈕三角形
            center_x = size // 2
            center_y = size // 2
            triangle_size = int(size * 0.25)

            # 播放按鈕三角形的頂點
            points = [
                (center_x - triangle_size // 2 + int(size * 0.05), center_y - triangle_size),
                (center_x - triangle_size // 2 + int(size * 0.05), center_y + triangle_size),
                (center_x + triangle_size + int(size * 0.05), center_y)
            ]
            draw.polygon(points, fill=(255, 255, 255, 255))

            return img

        # 生成各種尺寸的圖標
        sizes = [16, 32, 64, 128, 256, 512, 1024]

        for size in sizes:
            icon = create_icon(size)
            icon.save(iconset_path / f"icon_{size}x{size}.png")

            # 對於 Retina 顯示器，需要 @2x 版本
            if size <= 512:
                icon_2x = create_icon(size * 2)
                icon_2x.save(iconset_path / f"icon_{size}x{size}@2x.png")

        print("✅ PNG 圖標已創建")

        # 使用 iconutil 將 iconset 轉換為 icns
        icns_path = app_path / "AppIcon.icns"
        result = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_path), "-o", str(icns_path)],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"✅ 圖標已生成: {icns_path}")
            # 清理 iconset 目錄
            import shutil
            shutil.rmtree(iconset_path)
            return True
        else:
            print(f"❌ iconutil 錯誤: {result.stderr}")
            return False

    except ImportError:
        print("⚠️ 需要安裝 Pillow: pip3 install Pillow")
        print("正在嘗試安裝...")
        subprocess.run(["pip3", "install", "Pillow"], capture_output=True)
        print("請重新執行此腳本")
        return False

def copy_app_to_applications():
    """將應用程式複製到桌面"""
    script_dir = Path(__file__).parent
    app_path = script_dir / "YouTube字幕轉換器.app"
    desktop_path = Path.home() / "Desktop" / "YouTube字幕轉換器.app"

    if app_path.exists():
        import shutil
        if desktop_path.exists():
            shutil.rmtree(desktop_path)
        shutil.copytree(app_path, desktop_path)
        print(f"✅ 應用程式已複製到桌面: {desktop_path}")
        return True
    else:
        print(f"❌ 找不到應用程式: {app_path}")
        return False

if __name__ == "__main__":
    print("")
    print("=" * 50)
    print("  YouTube 字幕轉換器 - Mac 圖標設置")
    print("=" * 50)
    print("")

    # 創建圖標
    if create_youtube_icon():
        print("")
        print("圖標創建成功！")
        print("")

        # 詢問是否複製到桌面
        response = input("是否將應用程式複製到桌面？(y/n): ").strip().lower()
        if response == 'y':
            copy_app_to_applications()

    print("")
    print("設置完成！")
    print("")
