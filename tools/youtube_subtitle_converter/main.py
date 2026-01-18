#!/usr/bin/env python3
"""
YouTube 字幕轉換器
將 YouTube 影片轉換為帶有中英文字幕的版本

使用方式:
    python main.py "https://www.youtube.com/watch?v=VIDEO_ID"

或者作為模組使用:
    from main import YouTubeSubtitleConverter
    converter = YouTubeSubtitleConverter()
    result = converter.convert("https://www.youtube.com/watch?v=VIDEO_ID")
"""
import sys
import shutil
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import config, Config
from downloader import YouTubeDownloader, DownloadResult
from transcriber import GeminiTranscriber, TranscriptionResult
from subtitle import SubtitleGenerator
from embedder import SubtitleEmbedder, EmbedMode

console = Console()


@dataclass
class ConversionResult:
    """轉換結果"""
    output_video_path: Path
    chinese_subtitle_path: Path
    english_subtitle_path: Path
    bilingual_subtitle_path: Path
    video_title: str
    duration: int


class YouTubeSubtitleConverter:
    """YouTube 字幕轉換器主類別"""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        temp_dir: Optional[Path] = None,
        gemini_api_key: Optional[str] = None
    ):
        """
        初始化轉換器

        Args:
            output_dir: 輸出目錄
            temp_dir: 暫存目錄
            gemini_api_key: Gemini API 金鑰
        """
        self.output_dir = output_dir or config.OUTPUT_DIR
        self.temp_dir = temp_dir or config.TEMP_DIR

        # 初始化各個模組
        self.downloader = YouTubeDownloader(self.output_dir, self.temp_dir)
        self.transcriber = GeminiTranscriber(gemini_api_key)
        self.subtitle_generator = SubtitleGenerator(self.output_dir)
        self.embedder = SubtitleEmbedder()

        # 確保目錄存在
        Config.ensure_directories()

    def convert(
        self,
        youtube_url: str,
        quality: str = "720p",
        embed_mode: EmbedMode = EmbedMode.HARD,
        keep_temp_files: bool = False,
        source_lang: str = "en",
        target_lang: str = "zh-TW"
    ) -> ConversionResult:
        """
        轉換 YouTube 影片

        Args:
            youtube_url: YouTube 影片 URL
            quality: 影片品質
            embed_mode: 字幕嵌入模式
            keep_temp_files: 是否保留暫存檔案
            source_lang: 原始語言
            target_lang: 目標語言

        Returns:
            ConversionResult: 轉換結果
        """
        console.print(Panel.fit(
            f"[bold blue]YouTube 字幕轉換器[/bold blue]\n"
            f"URL: {youtube_url}",
            title="開始處理"
        ))

        try:
            # 步驟 1: 下載影片
            console.print("\n[bold]步驟 1/4: 下載影片[/bold]")
            download_result = self.downloader.download_video(
                youtube_url,
                quality=quality,
                download_subtitles=True
            )

            # 步驟 2: 轉錄和翻譯
            console.print("\n[bold]步驟 2/4: 語音辨識與翻譯[/bold]")
            audio_path = download_result.audio_path or download_result.video_path
            transcription_result = self.transcriber.transcribe_and_translate(
                audio_path,
                source_lang=source_lang,
                target_lang=target_lang,
                existing_subtitle_path=download_result.subtitle_path
            )

            # 步驟 3: 生成字幕檔案
            console.print("\n[bold]步驟 3/4: 生成字幕檔案[/bold]")
            safe_title = self._sanitize_filename(download_result.video_info.title)

            # 生成雙語字幕（中文在上，英文在下）
            bilingual_subtitle_path = self.output_dir / f"{safe_title}_bilingual.ass"
            self.subtitle_generator.generate_ass(
                transcription_result,
                bilingual_subtitle_path,
                include_original=True,
                include_translation=True
            )

            # 生成純中文字幕
            chinese_subtitle_path = self.output_dir / f"{safe_title}_zh.srt"
            self.subtitle_generator.generate_srt(
                transcription_result,
                chinese_subtitle_path,
                include_original=False,
                include_translation=True
            )

            # 生成純英文字幕
            english_subtitle_path = self.output_dir / f"{safe_title}_en.srt"
            self.subtitle_generator.generate_srt(
                transcription_result,
                english_subtitle_path,
                include_original=True,
                include_translation=False
            )

            # 步驟 4: 嵌入字幕
            console.print("\n[bold]步驟 4/4: 嵌入字幕[/bold]")
            output_video_path = self.output_dir / f"{safe_title}_subtitled.mp4"
            self.embedder.embed_subtitles(
                download_result.video_path,
                bilingual_subtitle_path,
                output_video_path,
                mode=embed_mode
            )

            # 清理暫存檔案
            if not keep_temp_files:
                self._cleanup_temp_files(download_result)

            # 顯示結果
            result = ConversionResult(
                output_video_path=output_video_path,
                chinese_subtitle_path=chinese_subtitle_path,
                english_subtitle_path=english_subtitle_path,
                bilingual_subtitle_path=bilingual_subtitle_path,
                video_title=download_result.video_info.title,
                duration=download_result.video_info.duration
            )

            self._display_result(result)
            return result

        except Exception as e:
            console.print(f"[red]錯誤: {e}[/red]")
            raise

    def _sanitize_filename(self, filename: str) -> str:
        """將檔案名稱轉換為安全格式"""
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        return filename[:100]

    def _cleanup_temp_files(self, download_result: DownloadResult):
        """清理暫存檔案"""
        console.print("[dim]正在清理暫存檔案...[/dim]")
        try:
            if download_result.video_path.exists():
                download_result.video_path.unlink()
            if download_result.audio_path and download_result.audio_path.exists():
                download_result.audio_path.unlink()
            if download_result.subtitle_path and download_result.subtitle_path.exists():
                download_result.subtitle_path.unlink()
        except Exception as e:
            console.print(f"[yellow]清理暫存檔案時發生警告: {e}[/yellow]")

    def _display_result(self, result: ConversionResult):
        """顯示轉換結果"""
        table = Table(title="轉換完成", show_header=True)
        table.add_column("項目", style="cyan")
        table.add_column("路徑", style="green")

        table.add_row("影片標題", result.video_title)
        table.add_row("影片長度", f"{result.duration // 60} 分 {result.duration % 60} 秒")
        table.add_row("輸出影片", str(result.output_video_path))
        table.add_row("中文字幕", str(result.chinese_subtitle_path))
        table.add_row("英文字幕", str(result.english_subtitle_path))
        table.add_row("雙語字幕", str(result.bilingual_subtitle_path))

        console.print()
        console.print(table)


@click.command()
@click.argument("youtube_url")
@click.option(
    "--quality", "-q",
    default="720p",
    help="影片品質 (如 720p, 1080p)"
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(),
    default="./output",
    help="輸出目錄"
)
@click.option(
    "--soft-subtitle",
    is_flag=True,
    help="使用軟字幕（可開關）而非硬字幕（燒錄）"
)
@click.option(
    "--keep-temp",
    is_flag=True,
    help="保留暫存檔案"
)
@click.option(
    "--source-lang",
    default="en",
    help="原始語言 (預設: en)"
)
@click.option(
    "--target-lang",
    default="zh-TW",
    help="目標語言 (預設: zh-TW)"
)
def main(
    youtube_url: str,
    quality: str,
    output_dir: str,
    soft_subtitle: bool,
    keep_temp: bool,
    source_lang: str,
    target_lang: str
):
    """
    YouTube 字幕轉換器

    將 YouTube 影片轉換為帶有中英文字幕的版本。

    使用範例:

        python main.py "https://www.youtube.com/watch?v=VIDEO_ID"

        python main.py "https://youtu.be/VIDEO_ID" -q 1080p -o ./videos
    """
    try:
        # 驗證設定
        Config.validate()

        converter = YouTubeSubtitleConverter(
            output_dir=Path(output_dir)
        )

        embed_mode = EmbedMode.SOFT if soft_subtitle else EmbedMode.HARD

        converter.convert(
            youtube_url,
            quality=quality,
            embed_mode=embed_mode,
            keep_temp_files=keep_temp,
            source_lang=source_lang,
            target_lang=target_lang
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]使用者中斷操作[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]錯誤: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
