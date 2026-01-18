"""
Gemini API 語音轉文字與翻譯模組
使用 Gemini 2.0 Flash 進行音訊處理和翻譯
"""
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

import google.generativeai as genai
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from config import config

console = Console()


@dataclass
class SubtitleEntry:
    """字幕條目"""
    index: int
    start_time: float  # 秒
    end_time: float  # 秒
    original_text: str
    translated_text: str = ""


@dataclass
class TranscriptionResult:
    """轉錄結果"""
    entries: List[SubtitleEntry] = field(default_factory=list)
    source_language: str = ""
    target_language: str = ""
    duration: float = 0.0


class GeminiTranscriber:
    """使用 Gemini API 進行語音轉錄和翻譯"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("請設定 GEMINI_API_KEY")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(config.GEMINI_MODEL)

    def transcribe_and_translate(
        self,
        audio_path: Path,
        source_lang: str = "en",
        target_lang: str = "zh-TW",
        existing_subtitle_path: Optional[Path] = None
    ) -> TranscriptionResult:
        """
        轉錄音訊並翻譯

        Args:
            audio_path: 音訊檔案路徑
            source_lang: 原始語言
            target_lang: 目標語言
            existing_subtitle_path: 現有字幕檔案路徑（如果有的話）

        Returns:
            TranscriptionResult: 轉錄結果
        """
        # 如果有現有字幕，直接翻譯
        if existing_subtitle_path and existing_subtitle_path.exists():
            console.print(f"[blue]使用現有字幕進行翻譯...[/blue]")
            return self._translate_existing_subtitles(
                existing_subtitle_path, source_lang, target_lang
            )

        # 否則進行完整的轉錄和翻譯
        console.print(f"[blue]使用 Gemini AI 進行語音辨識和翻譯...[/blue]")
        return self._transcribe_audio(audio_path, source_lang, target_lang)

    def _translate_existing_subtitles(
        self,
        subtitle_path: Path,
        source_lang: str,
        target_lang: str
    ) -> TranscriptionResult:
        """翻譯現有字幕"""
        entries = self._parse_srt(subtitle_path)

        if not entries:
            raise ValueError("無法解析字幕檔案")

        console.print(f"[blue]正在翻譯 {len(entries)} 條字幕...[/blue]")

        # 分批翻譯以避免 token 限制
        batch_size = 50
        translated_entries = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("翻譯中...", total=len(entries))

            for i in range(0, len(entries), batch_size):
                batch = entries[i:i + batch_size]
                translated_batch = self._translate_batch(batch, source_lang, target_lang)
                translated_entries.extend(translated_batch)
                progress.update(task, advance=len(batch))
                time.sleep(0.5)  # 避免 API 速率限制

        return TranscriptionResult(
            entries=translated_entries,
            source_language=source_lang,
            target_language=target_lang,
            duration=entries[-1].end_time if entries else 0.0
        )

    def _translate_batch(
        self,
        entries: List[SubtitleEntry],
        source_lang: str,
        target_lang: str
    ) -> List[SubtitleEntry]:
        """翻譯一批字幕"""
        # 準備翻譯文本
        texts = [entry.original_text for entry in entries]
        texts_json = json.dumps(texts, ensure_ascii=False)

        prompt = f"""請將以下 JSON 陣列中的字幕文字從 {source_lang} 翻譯成 {target_lang}（繁體中文）。

要求：
1. 保持原有的語氣和風格
2. 翻譯要自然流暢，符合中文表達習慣
3. 專有名詞可以保留原文或加上中文翻譯
4. 直接回傳翻譯後的 JSON 陣列，不要加任何其他文字

原文：
{texts_json}

翻譯後的 JSON 陣列："""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            # 清理回應（移除可能的 markdown 標記）
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            translated_texts = json.loads(response_text)

            # 更新字幕條目
            for entry, translated_text in zip(entries, translated_texts):
                entry.translated_text = translated_text

            return entries

        except Exception as e:
            console.print(f"[yellow]翻譯批次時發生錯誤: {e}[/yellow]")
            # 如果翻譯失敗，保留原文
            for entry in entries:
                entry.translated_text = entry.original_text
            return entries

    def _transcribe_audio(
        self,
        audio_path: Path,
        source_lang: str,
        target_lang: str
    ) -> TranscriptionResult:
        """使用 Gemini 轉錄音訊"""
        console.print(f"[blue]正在上傳音訊到 Gemini...[/blue]")

        # 上傳音訊檔案
        audio_file = genai.upload_file(str(audio_path))

        # 等待處理完成
        while audio_file.state.name == "PROCESSING":
            time.sleep(2)
            audio_file = genai.get_file(audio_file.name)

        if audio_file.state.name != "ACTIVE":
            raise RuntimeError(f"音訊處理失敗: {audio_file.state.name}")

        console.print(f"[blue]正在進行語音辨識和翻譯...[/blue]")

        prompt = f"""請聽這段音訊，並完成以下任務：

1. 將音訊內容轉錄成文字（{source_lang}）
2. 將轉錄的文字翻譯成 {target_lang}（繁體中文）
3. 為每段對話或句子提供時間戳

請以 JSON 格式輸出，格式如下：
{{
  "segments": [
    {{
      "start": 0.0,
      "end": 3.5,
      "original": "Hello, welcome to this video.",
      "translated": "大家好，歡迎收看這部影片。"
    }},
    ...
  ]
}}

注意：
- 時間戳以秒為單位
- 每個片段不要超過 10 秒
- 翻譯要自然流暢
- 只輸出 JSON，不要有其他文字"""

        try:
            response = self.model.generate_content([audio_file, prompt])
            response_text = response.text.strip()

            # 清理回應
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            result = json.loads(response_text)
            segments = result.get("segments", [])

            entries = []
            for i, seg in enumerate(segments, 1):
                entries.append(SubtitleEntry(
                    index=i,
                    start_time=float(seg.get("start", 0)),
                    end_time=float(seg.get("end", 0)),
                    original_text=seg.get("original", ""),
                    translated_text=seg.get("translated", "")
                ))

            # 清理上傳的檔案
            genai.delete_file(audio_file.name)

            return TranscriptionResult(
                entries=entries,
                source_language=source_lang,
                target_language=target_lang,
                duration=entries[-1].end_time if entries else 0.0
            )

        except Exception as e:
            console.print(f"[red]轉錄失敗: {e}[/red]")
            raise

    def _parse_srt(self, srt_path: Path) -> List[SubtitleEntry]:
        """解析 SRT 字幕檔"""
        entries = []

        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 分割字幕區塊
        blocks = content.strip().split('\n\n')

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue

            try:
                # 解析索引
                index = int(lines[0].strip())

                # 解析時間
                time_line = lines[1].strip()
                start_str, end_str = time_line.split(' --> ')
                start_time = self._parse_srt_time(start_str)
                end_time = self._parse_srt_time(end_str)

                # 解析文字
                text = ' '.join(lines[2:]).strip()

                entries.append(SubtitleEntry(
                    index=index,
                    start_time=start_time,
                    end_time=end_time,
                    original_text=text
                ))

            except (ValueError, IndexError) as e:
                continue

        return entries

    def _parse_srt_time(self, time_str: str) -> float:
        """將 SRT 時間格式轉換為秒"""
        # 格式: 00:00:00,000
        time_str = time_str.strip().replace(',', '.')
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
