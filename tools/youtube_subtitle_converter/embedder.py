"""
字幕嵌入模組
使用 FFmpeg 將字幕嵌入影片
"""
import subprocess
import shutil
from pathlib import Path
from typing import Optional
from enum import Enum

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

from config import config

console = Console()


class EmbedMode(Enum):
    """字幕嵌入模式"""
    SOFT = "soft"  # 軟字幕（可開關）
    HARD = "hard"  # 硬字幕（燒錄進影片）


class SubtitleEmbedder:
    """字幕嵌入器"""

    def __init__(self):
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """檢查 FFmpeg 是否可用"""
        if not shutil.which("ffmpeg"):
            raise RuntimeError(
                "找不到 FFmpeg，請先安裝 FFmpeg。\n"
                "Ubuntu/Debian: sudo apt install ffmpeg\n"
                "macOS: brew install ffmpeg\n"
                "Windows: 下載 https://ffmpeg.org/download.html"
            )

    def embed_subtitles(
        self,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path,
        mode: EmbedMode = EmbedMode.HARD,
        font_name: Optional[str] = None,
        font_size: Optional[int] = None
    ) -> Path:
        """
        將字幕嵌入影片

        Args:
            video_path: 影片檔案路徑
            subtitle_path: 字幕檔案路徑
            output_path: 輸出影片路徑
            mode: 嵌入模式（軟字幕或硬字幕）
            font_name: 字體名稱（僅硬字幕有效）
            font_size: 字體大小（僅硬字幕有效）

        Returns:
            Path: 輸出影片路徑
        """
        font_name = font_name or config.SUBTITLE_FONT
        font_size = font_size or config.SUBTITLE_FONT_SIZE

        if mode == EmbedMode.SOFT:
            return self._embed_soft_subtitles(video_path, subtitle_path, output_path)
        else:
            return self._embed_hard_subtitles(
                video_path, subtitle_path, output_path, font_name, font_size
            )

    def _embed_soft_subtitles(
        self,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path
    ) -> Path:
        """嵌入軟字幕（可開關的字幕軌道）"""
        console.print(f"[blue]正在嵌入軟字幕...[/blue]")

        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-i", str(subtitle_path),
            "-c", "copy",
            "-c:s", "mov_text",  # 使用 MP4 相容的字幕格式
            "-metadata:s:s:0", "language=chi",  # 設定字幕語言
            "-y",  # 覆蓋輸出檔案
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 錯誤: {result.stderr}")

        console.print(f"[green]✓ 軟字幕嵌入完成: {output_path}[/green]")
        return output_path

    def _embed_hard_subtitles(
        self,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path,
        font_name: str,
        font_size: int
    ) -> Path:
        """嵌入硬字幕（燒錄進影片）"""
        console.print(f"[blue]正在燒錄硬字幕（這可能需要一些時間）...[/blue]")

        # 獲取影片時長用於進度顯示
        duration = self._get_video_duration(video_path)

        # 根據字幕格式選擇濾鏡
        subtitle_ext = subtitle_path.suffix.lower()

        if subtitle_ext == ".ass":
            # ASS 字幕使用 ass 濾鏡
            subtitle_filter = f"ass='{self._escape_path(subtitle_path)}'"
        else:
            # SRT 字幕使用 subtitles 濾鏡
            # 設定字幕樣式
            style = (
                f"FontName={font_name},"
                f"FontSize={font_size},"
                f"PrimaryColour={config.SUBTITLE_PRIMARY_COLOR},"
                f"OutlineColour={config.SUBTITLE_OUTLINE_COLOR},"
                f"Outline={config.SUBTITLE_OUTLINE_WIDTH},"
                f"Shadow=1,"
                f"Alignment=2"  # 底部置中
            )
            subtitle_filter = f"subtitles='{self._escape_path(subtitle_path)}':force_style='{style}'"

        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", subtitle_filter,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            "-progress", "pipe:1",
            str(output_path)
        ]

        # 執行 FFmpeg 並顯示進度
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("燒錄字幕", total=duration)

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # 解析 FFmpeg 進度輸出
            current_time = 0
            for line in process.stdout:
                if line.startswith("out_time_ms="):
                    try:
                        time_ms = int(line.split("=")[1])
                        current_time = time_ms / 1000000
                        progress.update(task, completed=min(current_time, duration))
                    except:
                        pass

            process.wait()

            if process.returncode != 0:
                stderr = process.stderr.read()
                raise RuntimeError(f"FFmpeg 錯誤: {stderr}")

        console.print(f"[green]✓ 硬字幕燒錄完成: {output_path}[/green]")
        return output_path

    def _get_video_duration(self, video_path: Path) -> float:
        """獲取影片時長（秒）"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        try:
            return float(result.stdout.strip())
        except:
            return 0.0

    def _escape_path(self, path: Path) -> str:
        """轉義路徑中的特殊字元（用於 FFmpeg 濾鏡）"""
        path_str = str(path.absolute())
        # FFmpeg 濾鏡需要轉義的字元
        path_str = path_str.replace("\\", "/")
        path_str = path_str.replace(":", "\\:")
        path_str = path_str.replace("'", "\\'")
        return path_str

    def add_dual_subtitles(
        self,
        video_path: Path,
        chinese_subtitle_path: Path,
        english_subtitle_path: Path,
        output_path: Path
    ) -> Path:
        """
        添加雙語字幕（中文在下，英文在上）

        Args:
            video_path: 影片檔案路徑
            chinese_subtitle_path: 中文字幕路徑
            english_subtitle_path: 英文字幕路徑
            output_path: 輸出路徑

        Returns:
            Path: 輸出影片路徑
        """
        console.print(f"[blue]正在添加雙語字幕...[/blue]")

        # 使用複合濾鏡添加雙語字幕
        # 中文在下（較大字體），英文在上（較小字體）
        filter_complex = (
            f"subtitles='{self._escape_path(chinese_subtitle_path)}':"
            f"force_style='FontSize=24,Alignment=2,MarginV=30',"
            f"subtitles='{self._escape_path(english_subtitle_path)}':"
            f"force_style='FontSize=18,Alignment=2,MarginV=80'"
        )

        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", filter_complex,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 錯誤: {result.stderr}")

        console.print(f"[green]✓ 雙語字幕嵌入完成: {output_path}[/green]")
        return output_path
