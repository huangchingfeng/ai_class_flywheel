"""
設定管理模組
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()


class Config:
    """應用程式設定"""

    # Gemini API 設定
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

    # 檔案路徑設定
    BASE_DIR: Path = Path(__file__).parent
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./output"))
    TEMP_DIR: Path = Path(os.getenv("TEMP_DIR", "./temp"))

    # 影片處理設定
    MAX_VIDEO_DURATION: int = int(os.getenv("MAX_VIDEO_DURATION", "3600"))  # 秒
    VIDEO_QUALITY: str = os.getenv("VIDEO_QUALITY", "720p")

    # 字幕設定
    SUBTITLE_FONT: str = os.getenv("SUBTITLE_FONT", "Noto Sans CJK TC")
    SUBTITLE_FONT_SIZE: int = int(os.getenv("SUBTITLE_FONT_SIZE", "24"))
    SUBTITLE_PRIMARY_COLOR: str = os.getenv("SUBTITLE_PRIMARY_COLOR", "&HFFFFFF")  # 白色
    SUBTITLE_OUTLINE_COLOR: str = os.getenv("SUBTITLE_OUTLINE_COLOR", "&H000000")  # 黑色外框
    SUBTITLE_OUTLINE_WIDTH: int = int(os.getenv("SUBTITLE_OUTLINE_WIDTH", "2"))

    # 翻譯設定
    SOURCE_LANGUAGE: str = os.getenv("SOURCE_LANGUAGE", "en")  # 原始語言
    TARGET_LANGUAGE: str = os.getenv("TARGET_LANGUAGE", "zh-TW")  # 目標語言

    # 音訊分段設定（用於 Gemini API）
    AUDIO_CHUNK_DURATION: int = int(os.getenv("AUDIO_CHUNK_DURATION", "300"))  # 5 分鐘

    @classmethod
    def validate(cls) -> bool:
        """驗證必要設定"""
        if not cls.GEMINI_API_KEY:
            raise ValueError("請設定 GEMINI_API_KEY 環境變數")
        return True

    @classmethod
    def ensure_directories(cls):
        """確保必要目錄存在"""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)


# 預設設定實例
config = Config()
