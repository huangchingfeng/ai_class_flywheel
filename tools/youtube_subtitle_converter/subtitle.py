"""
字幕處理模組
處理字幕格式轉換和生成
"""
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from rich.console import Console

from transcriber import SubtitleEntry, TranscriptionResult

console = Console()


class SubtitleGenerator:
    """字幕生成器"""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("./output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_srt(
        self,
        result: TranscriptionResult,
        output_path: Path,
        include_original: bool = True,
        include_translation: bool = True
    ) -> Path:
        """
        生成 SRT 字幕檔

        Args:
            result: 轉錄結果
            output_path: 輸出路徑
            include_original: 是否包含原文
            include_translation: 是否包含翻譯

        Returns:
            Path: 生成的字幕檔路徑
        """
        lines = []

        for entry in result.entries:
            lines.append(str(entry.index))
            lines.append(f"{self._format_srt_time(entry.start_time)} --> {self._format_srt_time(entry.end_time)}")

            text_parts = []
            if include_translation and entry.translated_text:
                text_parts.append(entry.translated_text)
            if include_original and entry.original_text:
                text_parts.append(entry.original_text)

            lines.append('\n'.join(text_parts))
            lines.append('')

        content = '\n'.join(lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        console.print(f"[green]✓ SRT 字幕已生成: {output_path}[/green]")
        return output_path

    def generate_ass(
        self,
        result: TranscriptionResult,
        output_path: Path,
        font_name: str = "Noto Sans CJK TC",
        font_size: int = 24,
        primary_color: str = "&HFFFFFF",
        outline_color: str = "&H000000",
        outline_width: int = 2,
        include_original: bool = True,
        include_translation: bool = True
    ) -> Path:
        """
        生成 ASS 字幕檔（支援更多樣式選項）

        Args:
            result: 轉錄結果
            output_path: 輸出路徑
            font_name: 字體名稱
            font_size: 字體大小
            primary_color: 主要顏色 (ASS 格式)
            outline_color: 外框顏色 (ASS 格式)
            outline_width: 外框寬度
            include_original: 是否包含原文
            include_translation: 是否包含翻譯

        Returns:
            Path: 生成的字幕檔路徑
        """
        # ASS 檔案頭
        header = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Translation,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_width},1,2,10,10,30,1
Style: Original,{font_name},{int(font_size * 0.8)},&HCCCCCC,&H000000FF,{outline_color},&H80000000,0,0,0,0,100,100,0,0,1,{outline_width},1,8,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []

        for entry in result.entries:
            start = self._format_ass_time(entry.start_time)
            end = self._format_ass_time(entry.end_time)

            # 翻譯字幕（底部）
            if include_translation and entry.translated_text:
                text = entry.translated_text.replace('\n', '\\N')
                events.append(f"Dialogue: 0,{start},{end},Translation,,0,0,0,,{text}")

            # 原文字幕（頂部）
            if include_original and entry.original_text:
                text = entry.original_text.replace('\n', '\\N')
                events.append(f"Dialogue: 0,{start},{end},Original,,0,0,0,,{text}")

        content = header + '\n'.join(events)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        console.print(f"[green]✓ ASS 字幕已生成: {output_path}[/green]")
        return output_path

    def _format_srt_time(self, seconds: float) -> str:
        """將秒數轉換為 SRT 時間格式 (00:00:00,000)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_ass_time(self, seconds: float) -> str:
        """將秒數轉換為 ASS 時間格式 (0:00:00.00)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centis = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def merge_subtitles(
    original_entries: List[SubtitleEntry],
    translated_entries: List[SubtitleEntry]
) -> List[SubtitleEntry]:
    """
    合併原文和翻譯字幕

    Args:
        original_entries: 原文字幕條目
        translated_entries: 翻譯字幕條目

    Returns:
        合併後的字幕條目列表
    """
    # 假設兩個列表長度相同且對應
    merged = []
    for orig, trans in zip(original_entries, translated_entries):
        merged.append(SubtitleEntry(
            index=orig.index,
            start_time=orig.start_time,
            end_time=orig.end_time,
            original_text=orig.original_text,
            translated_text=trans.translated_text or trans.original_text
        ))
    return merged
