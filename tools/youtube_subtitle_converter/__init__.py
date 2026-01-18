"""
YouTube 字幕轉換器

將 YouTube 影片轉換為帶有中英文字幕的版本。
"""
from .main import YouTubeSubtitleConverter, ConversionResult
from .downloader import YouTubeDownloader, VideoInfo, DownloadResult
from .transcriber import GeminiTranscriber, TranscriptionResult, SubtitleEntry
from .subtitle import SubtitleGenerator
from .embedder import SubtitleEmbedder, EmbedMode
from .config import Config, config

__version__ = "1.0.0"
__all__ = [
    "YouTubeSubtitleConverter",
    "ConversionResult",
    "YouTubeDownloader",
    "VideoInfo",
    "DownloadResult",
    "GeminiTranscriber",
    "TranscriptionResult",
    "SubtitleEntry",
    "SubtitleGenerator",
    "SubtitleEmbedder",
    "EmbedMode",
    "Config",
    "config",
]
