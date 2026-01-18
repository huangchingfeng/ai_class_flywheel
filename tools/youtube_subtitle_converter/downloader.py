"""
YouTube 影片下載模組
使用 yt-dlp 下載 YouTube 影片和現有字幕
"""
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from rich.console import Console

from config import config

console = Console()


@dataclass
class VideoInfo:
    """影片資訊"""
    video_id: str
    title: str
    duration: int  # 秒
    uploader: str
    description: str
    available_subtitles: List[str]
    available_auto_subtitles: List[str]


@dataclass
class DownloadResult:
    """下載結果"""
    video_path: Path
    audio_path: Optional[Path]
    subtitle_path: Optional[Path]
    video_info: VideoInfo


class YouTubeDownloader:
    """YouTube 下載器"""

    def __init__(self, output_dir: Optional[Path] = None, temp_dir: Optional[Path] = None):
        self.output_dir = output_dir or config.OUTPUT_DIR
        self.temp_dir = temp_dir or config.TEMP_DIR
        self._ensure_directories()

    def _ensure_directories(self):
        """確保目錄存在"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_video_info(self, url: str) -> VideoInfo:
        """取得影片資訊"""
        console.print(f"[blue]正在獲取影片資訊...[/blue]")

        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"無法獲取影片資訊: {result.stderr}")

        info = json.loads(result.stdout)

        return VideoInfo(
            video_id=info.get("id", ""),
            title=info.get("title", ""),
            duration=info.get("duration", 0),
            uploader=info.get("uploader", ""),
            description=info.get("description", ""),
            available_subtitles=list(info.get("subtitles", {}).keys()),
            available_auto_subtitles=list(info.get("automatic_captions", {}).keys())
        )

    def download_video(
        self,
        url: str,
        quality: Optional[str] = None,
        download_subtitles: bool = True
    ) -> DownloadResult:
        """
        下載 YouTube 影片

        Args:
            url: YouTube 影片 URL
            quality: 影片品質 (如 "720p", "1080p")
            download_subtitles: 是否下載現有字幕

        Returns:
            DownloadResult: 下載結果
        """
        # 先獲取影片資訊
        video_info = self.get_video_info(url)

        console.print(f"[green]影片標題: {video_info.title}[/green]")
        console.print(f"[green]影片長度: {video_info.duration // 60} 分 {video_info.duration % 60} 秒[/green]")

        # 檢查影片長度
        if video_info.duration > config.MAX_VIDEO_DURATION:
            raise ValueError(
                f"影片長度 ({video_info.duration}秒) 超過限制 ({config.MAX_VIDEO_DURATION}秒)"
            )

        quality = quality or config.VIDEO_QUALITY

        # 建立安全的檔案名稱
        safe_title = self._sanitize_filename(video_info.title)
        video_path = self.temp_dir / f"{safe_title}.mp4"
        audio_path = self.temp_dir / f"{safe_title}.m4a"

        # 建立下載指令
        video_cmd = [
            "yt-dlp",
            "-f", f"bestvideo[height<={quality[:-1]}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality[:-1]}][ext=mp4]/best",
            "-o", str(video_path),
            "--merge-output-format", "mp4",
            url
        ]

        # 下載影片
        console.print(f"[blue]正在下載影片 ({quality})...[/blue]")
        result = subprocess.run(video_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            # 如果指定品質失敗，嘗試下載最佳可用品質
            console.print(f"[yellow]指定品質不可用，嘗試下載最佳品質...[/yellow]")
            video_cmd = [
                "yt-dlp",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "-o", str(video_path),
                "--merge-output-format", "mp4",
                url
            ]
            result = subprocess.run(video_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"下載影片失敗: {result.stderr}")

        # 下載音訊（用於語音辨識）
        console.print(f"[blue]正在提取音訊...[/blue]")
        audio_cmd = [
            "yt-dlp",
            "-f", "bestaudio[ext=m4a]/bestaudio",
            "-o", str(audio_path),
            url
        ]
        subprocess.run(audio_cmd, capture_output=True, text=True)

        # 嘗試下載現有字幕
        subtitle_path = None
        if download_subtitles and video_info.available_subtitles:
            subtitle_path = self._download_existing_subtitles(url, video_info, safe_title)

        console.print(f"[green]✓ 影片下載完成: {video_path}[/green]")

        return DownloadResult(
            video_path=video_path,
            audio_path=audio_path if audio_path.exists() else None,
            subtitle_path=subtitle_path,
            video_info=video_info
        )

    def _download_existing_subtitles(
        self,
        url: str,
        video_info: VideoInfo,
        safe_title: str
    ) -> Optional[Path]:
        """下載現有的字幕檔"""
        subtitle_path = self.temp_dir / f"{safe_title}.en.srt"

        # 優先下載英文字幕
        lang_priority = ["en", "en-US", "en-GB"]

        for lang in lang_priority:
            if lang in video_info.available_subtitles:
                console.print(f"[blue]正在下載 {lang} 字幕...[/blue]")
                cmd = [
                    "yt-dlp",
                    "--write-sub",
                    "--sub-lang", lang,
                    "--sub-format", "srt",
                    "--skip-download",
                    "-o", str(self.temp_dir / safe_title),
                    url
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0 and subtitle_path.exists():
                    console.print(f"[green]✓ 已下載現有字幕[/green]")
                    return subtitle_path

        # 嘗試自動產生的字幕
        for lang in lang_priority:
            if lang in video_info.available_auto_subtitles:
                console.print(f"[blue]正在下載自動產生的 {lang} 字幕...[/blue]")
                cmd = [
                    "yt-dlp",
                    "--write-auto-sub",
                    "--sub-lang", lang,
                    "--sub-format", "srt",
                    "--skip-download",
                    "-o", str(self.temp_dir / safe_title),
                    url
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)

                # 檢查各種可能的檔案名稱
                possible_paths = [
                    self.temp_dir / f"{safe_title}.{lang}.srt",
                    self.temp_dir / f"{safe_title}.srt"
                ]
                for path in possible_paths:
                    if path.exists():
                        console.print(f"[green]✓ 已下載自動產生字幕[/green]")
                        return path

        console.print(f"[yellow]找不到可用的字幕，將使用 AI 產生[/yellow]")
        return None

    def _sanitize_filename(self, filename: str) -> str:
        """將檔案名稱轉換為安全格式"""
        # 移除或替換不安全的字元
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        # 限制長度
        return filename[:100]

    def download_audio_only(self, url: str) -> Path:
        """只下載音訊（用於語音辨識）"""
        video_info = self.get_video_info(url)
        safe_title = self._sanitize_filename(video_info.title)
        audio_path = self.temp_dir / f"{safe_title}.m4a"

        console.print(f"[blue]正在下載音訊...[/blue]")
        cmd = [
            "yt-dlp",
            "-f", "bestaudio[ext=m4a]/bestaudio",
            "-o", str(audio_path),
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"下載音訊失敗: {result.stderr}")

        console.print(f"[green]✓ 音訊下載完成: {audio_path}[/green]")
        return audio_path
