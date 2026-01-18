#!/usr/bin/env python3
"""
YouTube 字幕轉換器 - 網頁介面
提供多種影片處理功能的 Web 應用程式
"""
import os
import sys
import json
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

import requests
import gradio as gr

# ==================== 設定 ====================

class Config:
    """應用程式設定"""
    GEMINI_API_KEY: str = "AIzaSyDbAyO-T-NJdylQR4W8cfwd78QPImNkDJY"
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    OUTPUT_DIR: Path = Path("./output")
    TEMP_DIR: Path = Path("./temp")

    @classmethod
    def set_api_key(cls, api_key: str):
        cls.GEMINI_API_KEY = api_key

    @classmethod
    def ensure_directories(cls):
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)

Config.ensure_directories()

# ==================== 工具函數 ====================

def sanitize_filename(filename: str) -> str:
    """將檔案名稱轉換為安全格式"""
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    return filename[:80]

def format_srt_time(seconds: float) -> str:
    """將秒數轉換為 SRT 時間格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def parse_srt_time(time_str: str) -> float:
    """將 SRT 時間格式轉換為秒"""
    time_str = time_str.strip().replace(',', '.')
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds

# ==================== YouTube 下載 ====================

def get_video_info(url: str) -> dict:
    """取得影片資訊"""
    cmd = ["yt-dlp", "--dump-json", "--no-download", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"無法獲取影片資訊: {result.stderr}")
    return json.loads(result.stdout)

def download_video(url: str, output_dir: Path, quality: str = "720p") -> Tuple[Path, dict]:
    """下載影片"""
    info = get_video_info(url)
    safe_title = sanitize_filename(info.get("title", "video"))
    video_path = output_dir / f"{safe_title}.mp4"

    cmd = [
        "yt-dlp",
        "-f", f"bestvideo[height<={quality[:-1]}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality[:-1]}][ext=mp4]/best",
        "-o", str(video_path),
        "--merge-output-format", "mp4",
        url
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # 嘗試下載最佳品質
        cmd = ["yt-dlp", "-f", "best[ext=mp4]/best", "-o", str(video_path), "--merge-output-format", "mp4", url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"下載失敗: {result.stderr}")

    return video_path, info

def download_audio(url: str, output_dir: Path) -> Tuple[Path, dict]:
    """下載音訊（MP3）"""
    info = get_video_info(url)
    safe_title = sanitize_filename(info.get("title", "audio"))
    audio_path = output_dir / f"{safe_title}.mp3"

    cmd = [
        "yt-dlp",
        "-x",  # 提取音訊
        "--audio-format", "mp3",
        "--audio-quality", "0",  # 最佳品質
        "-o", str(audio_path),
        url
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"下載音訊失敗: {result.stderr}")

    # yt-dlp 可能會改變副檔名
    if not audio_path.exists():
        possible_path = output_dir / f"{safe_title}.mp3"
        if possible_path.exists():
            audio_path = possible_path

    return audio_path, info

def download_existing_subtitles(url: str, output_dir: Path, lang: str = "en") -> Optional[Path]:
    """下載現有字幕"""
    info = get_video_info(url)
    safe_title = sanitize_filename(info.get("title", "video"))

    # 嘗試下載手動字幕
    cmd = [
        "yt-dlp",
        "--write-sub",
        "--sub-lang", lang,
        "--sub-format", "srt",
        "--skip-download",
        "-o", str(output_dir / safe_title),
        url
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    subtitle_path = output_dir / f"{safe_title}.{lang}.srt"
    if subtitle_path.exists():
        return subtitle_path

    # 嘗試自動字幕
    cmd = [
        "yt-dlp",
        "--write-auto-sub",
        "--sub-lang", lang,
        "--sub-format", "srt",
        "--skip-download",
        "-o", str(output_dir / safe_title),
        url
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    if subtitle_path.exists():
        return subtitle_path

    return None

# ==================== Gemini 翻譯（使用 REST API）====================

def call_gemini_api(prompt: str) -> str:
    """直接調用 Gemini REST API"""
    if not Config.GEMINI_API_KEY:
        raise ValueError("請先設定 Gemini API 金鑰")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.GEMINI_MODEL}:generateContent?key={Config.GEMINI_API_KEY}"

    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8192
        }
    }

    response = requests.post(url, headers=headers, json=data, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(f"Gemini API 錯誤: {response.text}")

    result = response.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]

def translate_subtitles(srt_content: str, source_lang: str = "en", target_lang: str = "zh-TW") -> list:
    """使用 Gemini 翻譯字幕"""
    # 解析 SRT
    blocks = srt_content.strip().split('\n\n')
    entries = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            try:
                index = int(lines[0].strip())
                time_line = lines[1].strip()
                text = ' '.join(lines[2:]).strip()
                entries.append({
                    'index': index,
                    'time': time_line,
                    'text': text
                })
            except:
                continue

    if not entries:
        return []

    # 分批翻譯
    batch_size = 30
    translated_entries = []

    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        texts = [e['text'] for e in batch]
        texts_json = json.dumps(texts, ensure_ascii=False)

        prompt = f"""請將以下 JSON 陣列中的字幕從 {source_lang} 翻譯成繁體中文。
要求：保持語氣、自然流暢、直接回傳 JSON 陣列，不要有其他文字。

原文：{texts_json}

翻譯後的 JSON 陣列："""

        try:
            response_text = call_gemini_api(prompt)
            response_text = response_text.strip()

            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            translated_texts = json.loads(response_text)

            for entry, trans in zip(batch, translated_texts):
                entry['translated'] = trans
                translated_entries.append(entry)
        except Exception as e:
            print(f"翻譯錯誤: {e}")
            for entry in batch:
                entry['translated'] = entry['text']
                translated_entries.append(entry)

        time.sleep(0.5)

    return translated_entries

def generate_srt(entries: list, include_original: bool = True, include_translation: bool = True) -> str:
    """生成 SRT 內容"""
    lines = []
    for entry in entries:
        lines.append(str(entry['index']))
        lines.append(entry['time'])

        text_parts = []
        if include_translation and entry.get('translated'):
            text_parts.append(entry['translated'])
        if include_original:
            text_parts.append(entry['text'])

        lines.append('\n'.join(text_parts))
        lines.append('')

    return '\n'.join(lines)

# ==================== 字幕嵌入 ====================

def embed_subtitles(video_path: Path, subtitle_path: Path, output_path: Path,
                   font_size: int = 24) -> Path:
    """將字幕嵌入影片"""
    # 轉義路徑
    sub_path_str = str(subtitle_path.absolute()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", f"subtitles='{sub_path_str}':force_style='FontSize={font_size},PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2'",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-y",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"嵌入字幕失敗: {result.stderr}")

    return output_path

# ==================== 主要功能 ====================

def process_bilingual_video(url: str, quality: str, progress=gr.Progress()) -> Tuple[str, str]:
    """功能1: 產生雙語字幕影片"""
    try:
        progress(0, desc="開始處理...")
        Config.ensure_directories()

        # 下載影片
        progress(0.1, desc="下載影片中...")
        video_path, info = download_video(url, Config.TEMP_DIR, quality)
        title = sanitize_filename(info.get("title", "video"))

        # 下載或生成字幕
        progress(0.3, desc="取得字幕中...")
        subtitle_path = download_existing_subtitles(url, Config.TEMP_DIR, "en")

        if subtitle_path and subtitle_path.exists():
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
        else:
            return None, "無法取得字幕，請確認影片有英文字幕"

        # 翻譯
        progress(0.5, desc="AI 翻譯中...")
        entries = translate_subtitles(srt_content)

        # 生成雙語字幕
        progress(0.7, desc="生成字幕檔...")
        bilingual_srt = generate_srt(entries, include_original=True, include_translation=True)
        bilingual_path = Config.TEMP_DIR / f"{title}_bilingual.srt"
        with open(bilingual_path, 'w', encoding='utf-8') as f:
            f.write(bilingual_srt)

        # 嵌入字幕
        progress(0.8, desc="嵌入字幕中（這需要一點時間）...")
        output_path = Config.OUTPUT_DIR / f"{title}_雙語字幕.mp4"
        embed_subtitles(video_path, bilingual_path, output_path)

        progress(1.0, desc="完成！")
        return str(output_path), f"✅ 完成！影片已儲存到：{output_path}"

    except Exception as e:
        return None, f"❌ 錯誤：{str(e)}"

def process_single_lang_video(url: str, quality: str, language: str, progress=gr.Progress()) -> Tuple[str, str]:
    """功能2: 產生單語字幕影片"""
    try:
        progress(0, desc="開始處理...")
        Config.ensure_directories()

        progress(0.1, desc="下載影片中...")
        video_path, info = download_video(url, Config.TEMP_DIR, quality)
        title = sanitize_filename(info.get("title", "video"))

        progress(0.3, desc="取得字幕中...")
        subtitle_path = download_existing_subtitles(url, Config.TEMP_DIR, "en")

        if not subtitle_path or not subtitle_path.exists():
            return None, "無法取得字幕"

        with open(subtitle_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()

        if language == "中文":
            progress(0.5, desc="AI 翻譯中...")
            entries = translate_subtitles(srt_content)
            final_srt = generate_srt(entries, include_original=False, include_translation=True)
            lang_label = "中文字幕"
        else:
            # 英文，直接使用原始字幕
            final_srt = srt_content
            lang_label = "英文字幕"

        progress(0.7, desc="生成字幕檔...")
        srt_path = Config.TEMP_DIR / f"{title}_{language}.srt"
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(final_srt)

        progress(0.8, desc="嵌入字幕中...")
        output_path = Config.OUTPUT_DIR / f"{title}_{lang_label}.mp4"
        embed_subtitles(video_path, srt_path, output_path)

        progress(1.0, desc="完成！")
        return str(output_path), f"✅ 完成！影片已儲存到：{output_path}"

    except Exception as e:
        return None, f"❌ 錯誤：{str(e)}"

def process_to_mp3(url: str, progress=gr.Progress()) -> Tuple[str, str]:
    """功能3: YouTube 轉 MP3"""
    try:
        progress(0, desc="開始處理...")
        Config.ensure_directories()

        progress(0.2, desc="下載並轉換音訊中...")
        audio_path, info = download_audio(url, Config.OUTPUT_DIR)

        progress(1.0, desc="完成！")
        return str(audio_path), f"✅ 完成！MP3 已儲存到：{audio_path}"

    except Exception as e:
        return None, f"❌ 錯誤：{str(e)}"

def process_subtitles_only(url: str, output_format: str, progress=gr.Progress()) -> Tuple[str, str, str, str]:
    """功能4: 只輸出字幕檔"""
    try:
        progress(0, desc="開始處理...")
        Config.ensure_directories()

        progress(0.2, desc="取得影片資訊...")
        info = get_video_info(url)
        title = sanitize_filename(info.get("title", "video"))

        progress(0.3, desc="下載字幕中...")
        subtitle_path = download_existing_subtitles(url, Config.TEMP_DIR, "en")

        if not subtitle_path or not subtitle_path.exists():
            return None, None, None, "無法取得字幕"

        with open(subtitle_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()

        progress(0.5, desc="AI 翻譯中...")
        entries = translate_subtitles(srt_content)

        progress(0.8, desc="生成字幕檔...")

        # 生成各種版本
        zh_srt = generate_srt(entries, include_original=False, include_translation=True)
        en_srt = generate_srt(entries, include_original=True, include_translation=False)
        bilingual_srt = generate_srt(entries, include_original=True, include_translation=True)

        zh_path = Config.OUTPUT_DIR / f"{title}_中文.srt"
        en_path = Config.OUTPUT_DIR / f"{title}_英文.srt"
        bilingual_path = Config.OUTPUT_DIR / f"{title}_雙語.srt"

        with open(zh_path, 'w', encoding='utf-8') as f:
            f.write(zh_srt)
        with open(en_path, 'w', encoding='utf-8') as f:
            f.write(en_srt)
        with open(bilingual_path, 'w', encoding='utf-8') as f:
            f.write(bilingual_srt)

        progress(1.0, desc="完成！")
        return str(zh_path), str(en_path), str(bilingual_path), f"✅ 完成！字幕檔已儲存到 {Config.OUTPUT_DIR}"

    except Exception as e:
        return None, None, None, f"❌ 錯誤：{str(e)}"

def save_api_key(api_key: str) -> str:
    """儲存 API 金鑰"""
    if not api_key or len(api_key) < 10:
        return "❌ 請輸入有效的 API 金鑰"
    Config.set_api_key(api_key)
    return "✅ API 金鑰已設定！"

# ==================== Gradio 介面 ====================

def create_ui():
    """建立 Gradio 介面"""

    with gr.Blocks(
        title="YouTube 字幕轉換器",
        theme=gr.themes.Soft(),
        css="""
        .main-title { text-align: center; margin-bottom: 20px; }
        .tab-content { padding: 20px; }
        """
    ) as app:

        gr.Markdown(
            """
            # 🎬 YouTube 字幕轉換器
            ### 輕鬆將 YouTube 影片轉換為帶有中英文字幕的版本
            """,
            elem_classes="main-title"
        )

        # API 金鑰設定
        with gr.Accordion("⚙️ 設定 Gemini API 金鑰（首次使用請先設定）", open=False):
            with gr.Row():
                api_key_input = gr.Textbox(
                    label="Gemini API 金鑰",
                    placeholder="輸入你的 API 金鑰...",
                    type="password",
                    scale=4
                )
                api_key_btn = gr.Button("儲存", scale=1)
            api_key_status = gr.Textbox(label="狀態", interactive=False)
            gr.Markdown("💡 可從 [Google AI Studio](https://aistudio.google.com/apikey) 免費取得 API 金鑰")

        api_key_btn.click(save_api_key, inputs=[api_key_input], outputs=[api_key_status])

        # 功能分頁
        with gr.Tabs():

            # 功能1: 雙語字幕影片
            with gr.Tab("🌐 雙語字幕影片"):
                gr.Markdown("### 將 YouTube 影片轉換為中英雙語字幕版本")
                with gr.Row():
                    url1 = gr.Textbox(label="YouTube 網址", placeholder="https://www.youtube.com/watch?v=...", scale=4)
                    quality1 = gr.Dropdown(choices=["480p", "720p", "1080p"], value="720p", label="畫質", scale=1)
                btn1 = gr.Button("🚀 開始轉換", variant="primary")
                output1_video = gr.File(label="下載影片")
                output1_status = gr.Textbox(label="狀態")

                btn1.click(process_bilingual_video, inputs=[url1, quality1], outputs=[output1_video, output1_status])

            # 功能2: 單語字幕影片
            with gr.Tab("🔤 單語字幕影片"):
                gr.Markdown("### 將 YouTube 影片轉換為單一語言字幕版本")
                with gr.Row():
                    url2 = gr.Textbox(label="YouTube 網址", placeholder="https://www.youtube.com/watch?v=...", scale=3)
                    quality2 = gr.Dropdown(choices=["480p", "720p", "1080p"], value="720p", label="畫質", scale=1)
                    lang2 = gr.Dropdown(choices=["中文", "英文"], value="中文", label="字幕語言", scale=1)
                btn2 = gr.Button("🚀 開始轉換", variant="primary")
                output2_video = gr.File(label="下載影片")
                output2_status = gr.Textbox(label="狀態")

                btn2.click(process_single_lang_video, inputs=[url2, quality2, lang2], outputs=[output2_video, output2_status])

            # 功能3: YouTube 轉 MP3
            with gr.Tab("🎵 YouTube 轉 MP3"):
                gr.Markdown("### 將 YouTube 影片轉換為 MP3 音訊檔")
                url3 = gr.Textbox(label="YouTube 網址", placeholder="https://www.youtube.com/watch?v=...")
                btn3 = gr.Button("🚀 開始轉換", variant="primary")
                output3_audio = gr.File(label="下載 MP3")
                output3_status = gr.Textbox(label="狀態")

                btn3.click(process_to_mp3, inputs=[url3], outputs=[output3_audio, output3_status])

            # 功能4: 只要字幕檔
            with gr.Tab("📝 只要字幕檔"):
                gr.Markdown("### 取得 YouTube 影片的字幕檔（不下載影片）")
                url4 = gr.Textbox(label="YouTube 網址", placeholder="https://www.youtube.com/watch?v=...")
                format4 = gr.Dropdown(choices=["SRT"], value="SRT", label="字幕格式")
                btn4 = gr.Button("🚀 開始轉換", variant="primary")
                with gr.Row():
                    output4_zh = gr.File(label="中文字幕")
                    output4_en = gr.File(label="英文字幕")
                    output4_bilingual = gr.File(label="雙語字幕")
                output4_status = gr.Textbox(label="狀態")

                btn4.click(process_subtitles_only, inputs=[url4, format4], outputs=[output4_zh, output4_en, output4_bilingual, output4_status])

        gr.Markdown(
            """
            ---
            ### 使用說明
            1. **首次使用**：請先在上方設定 Gemini API 金鑰
            2. **貼上網址**：將 YouTube 影片網址貼到輸入框
            3. **選擇功能**：切換不同分頁選擇你需要的功能
            4. **等待處理**：點擊開始後等待處理完成
            5. **下載檔案**：處理完成後點擊下載

            ⚠️ **注意事項**：
            - 影片長度建議在 30 分鐘以內
            - 需要影片本身有英文字幕才能翻譯
            - 處理時間依影片長度而定
            """
        )

    return app

# ==================== 主程式 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("🎬 YouTube 字幕轉換器")
    print("=" * 50)
    print()
    print("正在啟動網頁介面...")
    print()

    app = create_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        inbrowser=False
    )
