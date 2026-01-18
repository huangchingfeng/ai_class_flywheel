#!/usr/bin/env python3
"""
YouTube 字幕轉換器 - 網頁介面
提供多種影片處理功能的 Web 應用程式
支援多語言翻譯
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

# 支援的語言列表
SUPPORTED_LANGUAGES = {
    "中文（繁體）": "zh-TW",
    "中文（簡體）": "zh-CN",
    "英文": "en",
    "日文": "ja",
    "韓文": "ko",
    "法文": "fr",
    "德文": "de",
    "西班牙文": "es",
    "葡萄牙文": "pt",
    "俄文": "ru",
    "義大利文": "it",
    "荷蘭文": "nl",
    "阿拉伯文": "ar",
    "印地文": "hi",
    "泰文": "th",
    "越南文": "vi",
    "印尼文": "id",
    "馬來文": "ms",
}

# 語言代碼到名稱的映射
LANG_CODE_TO_NAME = {v: k for k, v in SUPPORTED_LANGUAGES.items()}

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

# ==================== YouTube 下載 ====================

def get_video_info(url: str) -> dict:
    """取得影片資訊"""
    cmd = ["yt-dlp", "--dump-json", "--no-download", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"無法獲取影片資訊: {result.stderr}")
    return json.loads(result.stdout)

def get_available_subtitles(url: str) -> Tuple[List[str], List[str]]:
    """取得可用的字幕語言列表"""
    info = get_video_info(url)
    manual_subs = list(info.get("subtitles", {}).keys())
    auto_subs = list(info.get("automatic_captions", {}).keys())
    return manual_subs, auto_subs

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
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", str(audio_path),
        url
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"下載音訊失敗: {result.stderr}")

    return audio_path, info

def download_subtitles_any_language(url: str, output_dir: Path, preferred_lang: str = None) -> Tuple[Optional[Path], str]:
    """
    下載字幕（支援任何語言）

    Returns:
        Tuple[Optional[Path], str]: (字幕檔路徑, 偵測到的語言代碼)
    """
    info = get_video_info(url)
    safe_title = sanitize_filename(info.get("title", "video"))

    manual_subs = info.get("subtitles", {})
    auto_subs = info.get("automatic_captions", {})

    # 優先順序：指定語言 > 手動字幕 > 自動字幕
    lang_to_try = []

    if preferred_lang:
        lang_to_try.append(preferred_lang)

    # 添加所有可用的手動字幕語言
    for lang in manual_subs.keys():
        if lang not in lang_to_try:
            lang_to_try.append(lang)

    # 添加所有可用的自動字幕語言
    for lang in auto_subs.keys():
        if lang not in lang_to_try:
            lang_to_try.append(lang)

    # 嘗試下載
    for lang in lang_to_try:
        subtitle_path = output_dir / f"{safe_title}.{lang}.srt"

        # 先嘗試手動字幕
        if lang in manual_subs:
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

            if subtitle_path.exists():
                return subtitle_path, lang

        # 嘗試自動字幕
        if lang in auto_subs:
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
                return subtitle_path, lang

    return None, ""

# ==================== Gemini API ====================

def upload_file_to_gemini(file_path: Path) -> str:
    """上傳檔案到 Gemini File API"""
    if not Config.GEMINI_API_KEY:
        raise ValueError("請先設定 Gemini API 金鑰")

    # 上傳檔案
    upload_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={Config.GEMINI_API_KEY}"

    with open(file_path, 'rb') as f:
        file_content = f.read()

    # 確定 MIME 類型
    suffix = file_path.suffix.lower()
    mime_types = {
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/mp4',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.flac': 'audio/flac',
    }
    mime_type = mime_types.get(suffix, 'audio/mpeg')

    headers = {
        'X-Goog-Upload-Command': 'start, upload, finalize',
        'X-Goog-Upload-Header-Content-Length': str(len(file_content)),
        'X-Goog-Upload-Header-Content-Type': mime_type,
        'Content-Type': 'application/json',
    }

    metadata = json.dumps({'file': {'display_name': file_path.name}})

    # 使用 multipart upload
    response = requests.post(
        upload_url,
        headers={
            'X-Goog-Upload-Protocol': 'resumable',
            'X-Goog-Upload-Command': 'start',
            'X-Goog-Upload-Header-Content-Length': str(len(file_content)),
            'X-Goog-Upload-Header-Content-Type': mime_type,
            'Content-Type': 'application/json',
        },
        data=metadata,
        timeout=60
    )

    if response.status_code != 200:
        raise RuntimeError(f"上傳初始化失敗: {response.text}")

    upload_uri = response.headers.get('X-Goog-Upload-URL')

    # 上傳檔案內容
    response = requests.post(
        upload_uri,
        headers={
            'X-Goog-Upload-Command': 'upload, finalize',
            'X-Goog-Upload-Offset': '0',
            'Content-Type': mime_type,
        },
        data=file_content,
        timeout=300
    )

    if response.status_code != 200:
        raise RuntimeError(f"檔案上傳失敗: {response.text}")

    result = response.json()
    return result['file']['uri']

def transcribe_audio_with_gemini(audio_path: Path, source_lang: str = "en") -> str:
    """使用 Gemini 進行語音辨識，產生 SRT 格式字幕"""
    if not Config.GEMINI_API_KEY:
        raise ValueError("請先設定 Gemini API 金鑰")

    print(f"正在上傳音訊檔案進行語音辨識...")

    # 上傳檔案
    file_uri = upload_file_to_gemini(audio_path)

    print(f"檔案已上傳，正在進行語音辨識...")

    # 使用 Gemini 進行語音辨識
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.GEMINI_MODEL}:generateContent?key={Config.GEMINI_API_KEY}"

    source_name = get_language_name(source_lang)

    prompt = f"""請聽這段音訊，並將其轉錄成文字。

要求：
1. 辨識音訊中的{source_name}語音內容
2. 產生 SRT 字幕格式
3. 每段字幕約 5-10 秒
4. 時間戳格式：00:00:00,000 --> 00:00:05,000
5. 只輸出 SRT 格式內容，不要有其他說明文字

輸出格式範例：
1
00:00:00,000 --> 00:00:05,000
第一段字幕內容

2
00:00:05,000 --> 00:00:10,000
第二段字幕內容

請開始轉錄："""

    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [
                {"file_data": {"mime_type": "audio/mpeg", "file_uri": file_uri}},
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192
        }
    }

    response = requests.post(url, headers=headers, json=data, timeout=300)

    if response.status_code != 200:
        raise RuntimeError(f"語音辨識失敗: {response.text}")

    result = response.json()
    srt_content = result["candidates"][0]["content"]["parts"][0]["text"]

    # 清理可能的 markdown 標記
    if srt_content.startswith("```"):
        lines = srt_content.split("\n")
        srt_content = "\n".join(lines[1:-1])

    return srt_content

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

    response = requests.post(url, headers=headers, json=data, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(f"Gemini API 錯誤: {response.text}")

    result = response.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]

def get_language_name(lang_code: str) -> str:
    """取得語言名稱"""
    lang_names = {
        "zh-TW": "繁體中文",
        "zh-CN": "簡體中文",
        "en": "英文",
        "ja": "日文",
        "ko": "韓文",
        "fr": "法文",
        "de": "德文",
        "es": "西班牙文",
        "pt": "葡萄牙文",
        "ru": "俄文",
        "it": "義大利文",
        "nl": "荷蘭文",
        "ar": "阿拉伯文",
        "hi": "印地文",
        "th": "泰文",
        "vi": "越南文",
        "id": "印尼文",
        "ms": "馬來文",
    }
    return lang_names.get(lang_code, lang_code)

def translate_subtitles(srt_content: str, source_lang: str, target_lang: str) -> list:
    """使用 Gemini 翻譯字幕（支援任意語言對）"""
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

    source_name = get_language_name(source_lang)
    target_name = get_language_name(target_lang)

    # 分批翻譯
    batch_size = 30
    translated_entries = []

    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        texts = [e['text'] for e in batch]
        texts_json = json.dumps(texts, ensure_ascii=False)

        prompt = f"""請將以下 JSON 陣列中的字幕從「{source_name}」翻譯成「{target_name}」。
要求：
1. 保持原有的語氣和風格
2. 翻譯要自然流暢
3. 直接回傳 JSON 陣列，不要有其他文字或 markdown 標記

原文：{texts_json}

翻譯後的 JSON 陣列："""

        try:
            response_text = call_gemini_api(prompt)
            response_text = response_text.strip()

            # 清理可能的 markdown 標記
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
            if response_text.startswith("json"):
                response_text = response_text[4:]

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
    """將字幕嵌入影片（使用安全的臨時檔案避免特殊字元問題）"""
    import uuid

    # 建立安全的工作目錄和檔案名稱
    work_dir = Config.TEMP_DIR / f"work_{uuid.uuid4().hex}"
    work_dir.mkdir(parents=True, exist_ok=True)

    safe_video = work_dir / "input.mp4"
    safe_subtitle = work_dir / "subtitle.srt"
    safe_output = work_dir / "output.mp4"

    try:
        # 複製檔案到安全路徑
        shutil.copy2(video_path, safe_video)
        shutil.copy2(subtitle_path, safe_subtitle)

        # 在工作目錄中執行 FFmpeg，使用相對路徑
        # 這樣可以完全避免路徑中的特殊字元問題
        cmd = [
            "ffmpeg",
            "-i", "input.mp4",
            "-vf", f"subtitles=subtitle.srt:force_style='FontSize={font_size}'",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            "output.mp4"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(work_dir))
        if result.returncode != 0:
            raise RuntimeError(f"嵌入字幕失敗: {result.stderr}")

        # 複製輸出檔案到目標位置
        shutil.copy2(safe_output, output_path)

        return output_path
    finally:
        # 清理工作目錄
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)

# ==================== 主要功能 ====================

def process_bilingual_video(url: str, quality: str, source_lang: str, target_lang: str, progress=gr.Progress()) -> Tuple[str, str]:
    """功能1: 產生雙語字幕影片"""
    try:
        progress(0, desc="開始處理...")
        Config.ensure_directories()

        source_code = SUPPORTED_LANGUAGES.get(source_lang, "en")
        target_code = SUPPORTED_LANGUAGES.get(target_lang, "zh-TW")

        progress(0.1, desc="下載影片中...")
        video_path, info = download_video(url, Config.TEMP_DIR, quality)
        title = sanitize_filename(info.get("title", "video"))

        progress(0.2, desc="取得字幕中...")
        subtitle_path, detected_lang = download_subtitles_any_language(url, Config.TEMP_DIR, source_code)

        if subtitle_path and subtitle_path.exists():
            # 有現有字幕，直接使用
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
        else:
            # 沒有現有字幕，使用 AI 語音辨識
            progress(0.3, desc="沒有找到現有字幕，正在下載音訊...")
            audio_path, _ = download_audio(url, Config.TEMP_DIR)

            progress(0.4, desc="AI 語音辨識中（這可能需要幾分鐘）...")
            srt_content = transcribe_audio_with_gemini(audio_path, source_code)
            detected_lang = source_code

        progress(0.5, desc=f"AI 翻譯中（{source_lang} → {target_lang}）...")
        entries = translate_subtitles(srt_content, detected_lang, target_code)

        progress(0.7, desc="生成字幕檔...")
        bilingual_srt = generate_srt(entries, include_original=True, include_translation=True)
        bilingual_path = Config.TEMP_DIR / f"{title}_bilingual.srt"
        with open(bilingual_path, 'w', encoding='utf-8') as f:
            f.write(bilingual_srt)

        progress(0.8, desc="嵌入字幕中（這需要一點時間）...")
        output_path = Config.OUTPUT_DIR / f"{title}_雙語字幕.mp4"
        embed_subtitles(video_path, bilingual_path, output_path)

        progress(1.0, desc="完成！")
        return str(output_path), f"✅ 完成！影片已儲存到：{output_path}"

    except Exception as e:
        return None, f"❌ 錯誤：{str(e)}"

def process_single_lang_video(url: str, quality: str, source_lang: str, target_lang: str, progress=gr.Progress()) -> Tuple[str, str]:
    """功能2: 產生單語字幕影片"""
    try:
        progress(0, desc="開始處理...")
        Config.ensure_directories()

        source_code = SUPPORTED_LANGUAGES.get(source_lang, "en")
        target_code = SUPPORTED_LANGUAGES.get(target_lang, "zh-TW")

        progress(0.1, desc="下載影片中...")
        video_path, info = download_video(url, Config.TEMP_DIR, quality)
        title = sanitize_filename(info.get("title", "video"))

        progress(0.2, desc="取得字幕中...")
        subtitle_path, detected_lang = download_subtitles_any_language(url, Config.TEMP_DIR, source_code)

        if subtitle_path and subtitle_path.exists():
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
        else:
            # 沒有現有字幕，使用 AI 語音辨識
            progress(0.3, desc="沒有找到現有字幕，正在下載音訊...")
            audio_path, _ = download_audio(url, Config.TEMP_DIR)

            progress(0.4, desc="AI 語音辨識中（這可能需要幾分鐘）...")
            srt_content = transcribe_audio_with_gemini(audio_path, source_code)
            detected_lang = source_code

        # 如果來源和目標語言相同，不需要翻譯
        if source_code == target_code:
            final_srt = srt_content
        else:
            progress(0.5, desc=f"AI 翻譯中（{source_lang} → {target_lang}）...")
            entries = translate_subtitles(srt_content, detected_lang, target_code)
            final_srt = generate_srt(entries, include_original=False, include_translation=True)

        progress(0.7, desc="生成字幕檔...")
        srt_path = Config.TEMP_DIR / f"{title}_{target_lang}.srt"
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(final_srt)

        progress(0.8, desc="嵌入字幕中...")
        output_path = Config.OUTPUT_DIR / f"{title}_{target_lang}字幕.mp4"
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

def process_subtitles_only(url: str, source_lang: str, target_langs: list, progress=gr.Progress()) -> Tuple[str, str, str, str, str]:
    """功能4: 只輸出字幕檔（支援多語言）"""
    try:
        progress(0, desc="開始處理...")
        Config.ensure_directories()

        source_code = SUPPORTED_LANGUAGES.get(source_lang, "en")

        # 處理多語言選擇
        if not target_langs:
            target_langs = ["中文（繁體）"]

        progress(0.1, desc="取得影片資訊...")
        info = get_video_info(url)
        title = sanitize_filename(info.get("title", "video"))

        progress(0.2, desc="下載字幕中...")
        subtitle_path, detected_lang = download_subtitles_any_language(url, Config.TEMP_DIR, source_code)

        if subtitle_path and subtitle_path.exists():
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
        else:
            # 沒有現有字幕，使用 AI 語音辨識
            progress(0.25, desc="沒有找到現有字幕，正在下載音訊...")
            audio_path, _ = download_audio(url, Config.TEMP_DIR)

            progress(0.3, desc="AI 語音辨識中（這可能需要幾分鐘）...")
            srt_content = transcribe_audio_with_gemini(audio_path, source_code)
            detected_lang = source_code

        # 儲存原始字幕
        original_srt_path = Config.OUTPUT_DIR / f"{title}_原始_{source_lang}.srt"
        with open(original_srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        # 翻譯成多種語言
        all_results = []
        all_results.append(f"📄 **原始字幕 ({source_lang})**\n```\n{srt_content[:2000]}{'...(truncated)' if len(srt_content) > 2000 else ''}\n```\n")

        saved_files = [str(original_srt_path)]

        total_langs = len(target_langs)
        for i, target_lang in enumerate(target_langs):
            target_code = SUPPORTED_LANGUAGES.get(target_lang, "zh-TW")

            progress_val = 0.4 + (0.5 * i / total_langs)
            progress(progress_val, desc=f"AI 翻譯中（{source_lang} → {target_lang}）... ({i+1}/{total_langs})")

            entries = translate_subtitles(srt_content, detected_lang, target_code)
            translated_srt = generate_srt(entries, include_original=False, include_translation=True)

            # 儲存翻譯後的字幕
            translated_path = Config.OUTPUT_DIR / f"{title}_{target_lang}.srt"
            with open(translated_path, 'w', encoding='utf-8') as f:
                f.write(translated_srt)
            saved_files.append(str(translated_path))

            # 加入結果顯示
            all_results.append(f"🌐 **{target_lang} 翻譯**\n```\n{translated_srt[:2000]}{'...(truncated)' if len(translated_srt) > 2000 else ''}\n```\n")

        progress(1.0, desc="完成！")

        results_text = "\n---\n".join(all_results)
        files_text = "\n".join([f"- {f}" for f in saved_files])
        status = f"✅ 完成！已翻譯成 {total_langs} 種語言\n\n📁 已儲存的檔案：\n{files_text}"

        return results_text, status

    except Exception as e:
        return f"❌ 錯誤：{str(e)}", f"❌ 錯誤：{str(e)}"

def save_api_key(api_key: str) -> str:
    """儲存 API 金鑰"""
    if not api_key or len(api_key) < 10:
        return "❌ 請輸入有效的 API 金鑰"
    Config.set_api_key(api_key)
    return "✅ API 金鑰已設定！"

# ==================== Gradio 介面 ====================

def create_ui():
    """建立 Gradio 介面"""

    lang_choices = list(SUPPORTED_LANGUAGES.keys())

    with gr.Blocks(
        title="YouTube 字幕轉換器",
        theme=gr.themes.Soft(),
    ) as app:

        gr.Markdown(
            """
            # 🎬 YouTube 字幕轉換器
            ### 輕鬆將 YouTube 影片字幕翻譯成任何語言
            """
        )

        # API 金鑰設定
        with gr.Accordion("⚙️ 設定 Gemini API 金鑰（已預設，可略過）", open=False):
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
                gr.Markdown("### 將 YouTube 影片轉換為雙語字幕版本")
                url1 = gr.Textbox(label="YouTube 網址", placeholder="https://www.youtube.com/watch?v=...")
                with gr.Row():
                    source_lang1 = gr.Dropdown(choices=lang_choices, value="英文", label="原始字幕語言", scale=1)
                    target_lang1 = gr.Dropdown(choices=lang_choices, value="中文（繁體）", label="翻譯成", scale=1)
                    quality1 = gr.Dropdown(choices=["480p", "720p", "1080p"], value="720p", label="畫質", scale=1)
                btn1 = gr.Button("🚀 開始轉換", variant="primary")
                output1_video = gr.File(label="下載影片")
                output1_status = gr.Textbox(label="狀態")

                btn1.click(process_bilingual_video, inputs=[url1, quality1, source_lang1, target_lang1], outputs=[output1_video, output1_status])

            # 功能2: 單語字幕影片
            with gr.Tab("🔤 單語字幕影片"):
                gr.Markdown("### 將 YouTube 影片轉換為單一語言字幕版本")
                url2 = gr.Textbox(label="YouTube 網址", placeholder="https://www.youtube.com/watch?v=...")
                with gr.Row():
                    source_lang2 = gr.Dropdown(choices=lang_choices, value="英文", label="原始字幕語言", scale=1)
                    target_lang2 = gr.Dropdown(choices=lang_choices, value="中文（繁體）", label="翻譯成", scale=1)
                    quality2 = gr.Dropdown(choices=["480p", "720p", "1080p"], value="720p", label="畫質", scale=1)
                btn2 = gr.Button("🚀 開始轉換", variant="primary")
                output2_video = gr.File(label="下載影片")
                output2_status = gr.Textbox(label="狀態")

                btn2.click(process_single_lang_video, inputs=[url2, quality2, source_lang2, target_lang2], outputs=[output2_video, output2_status])

            # 功能3: YouTube 轉 MP3
            with gr.Tab("🎵 YouTube 轉 MP3"):
                gr.Markdown("### 將 YouTube 影片轉換為 MP3 音訊檔")
                url3 = gr.Textbox(label="YouTube 網址", placeholder="https://www.youtube.com/watch?v=...")
                btn3 = gr.Button("🚀 開始轉換", variant="primary")
                output3_audio = gr.File(label="下載 MP3")
                output3_status = gr.Textbox(label="狀態")

                btn3.click(process_to_mp3, inputs=[url3], outputs=[output3_audio, output3_status])

            # 功能4: 只要字幕檔（多語言）
            with gr.Tab("📝 只要字幕檔"):
                gr.Markdown("### 取得 YouTube 影片的字幕檔（支援多語言翻譯）")
                url4 = gr.Textbox(label="YouTube 網址", placeholder="https://www.youtube.com/watch?v=...")
                with gr.Row():
                    source_lang4 = gr.Dropdown(choices=lang_choices, value="英文", label="原始字幕語言", scale=1)
                    target_langs4 = gr.Dropdown(
                        choices=lang_choices,
                        value=["中文（繁體）"],
                        label="翻譯成（可多選）",
                        multiselect=True,
                        scale=2
                    )
                btn4 = gr.Button("🚀 開始翻譯", variant="primary")
                output4_status = gr.Textbox(label="狀態", lines=6)
                gr.Markdown("### 翻譯結果預覽")
                output4_results = gr.Markdown(label="翻譯結果")

                btn4.click(
                    process_subtitles_only,
                    inputs=[url4, source_lang4, target_langs4],
                    outputs=[output4_results, output4_status]
                )

        gr.Markdown(
            """
            ---
            ### 使用說明
            1. **貼上網址**：將 YouTube 影片網址貼到輸入框
            2. **選擇語言**：選擇原始語言和要翻譯成的語言
            3. **開始轉換**：點擊按鈕等待處理完成
            4. **下載檔案**：處理完成後點擊下載

            ### 支援語言
            中文（繁體/簡體）、英文、日文、韓文、法文、德文、西班牙文、葡萄牙文、俄文、義大利文、荷蘭文、阿拉伯文、印地文、泰文、越南文、印尼文、馬來文

            ### 智慧字幕處理
            - ✅ 有現有字幕：直接下載並翻譯（速度較快）
            - ✅ 沒有字幕：自動使用 AI 語音辨識產生字幕（需要較長時間）
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
