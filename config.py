
import os
import sys

# UI Colors
BG_COLOR = "#2B2B2B"
ACCENT_COLOR = "#1F6AA5"
TEXT_COLOR = "#FFFFFF"
SECONDARY_TEXT_COLOR = "#A0A0A0"
NEON_BLUE = "#00F2FF" # Neon blue for cyber vibe

# App Info
APP_NAME = "NeoRecorder"
VERSION = "1.2.0"
AUTHOR = "DimSimd"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Paths for internal assets (bundled)
ASSETS_DIR = resource_path("assets")
LANG_DIR = os.path.join(ASSETS_DIR, "lang")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")

# Paths for external files (next to EXE)
if hasattr(sys, 'frozen'):
    EXE_DIR = os.path.dirname(sys.executable)
else:
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))

# Default Settings
DEFAULT_LANG = "ru"
DEFAULT_FORMAT = "mp4"

# Recording Settings
DEFAULT_FPS = 60
FPS_OPTIONS = [30, 60, 120, 144, 240]

# Quality Presets: name -> (crf, preset)
QUALITY_PRESETS = {
    "ultrafast": {"crf": 23, "preset": "ultrafast", "label_ru": "Быстрая", "label_en": "Fast"},
    "balanced": {"crf": 20, "preset": "fast", "label_ru": "Баланс", "label_en": "Balanced"},
    "quality": {"crf": 18, "preset": "medium", "label_ru": "Качество", "label_en": "Quality"},
    "lossless": {"crf": 0, "preset": "ultrafast", "label_ru": "Без потерь", "label_en": "Lossless"},
}
DEFAULT_QUALITY = "balanced"

# Hardware Encoder preference (auto-detected at runtime)
USE_HARDWARE_ENCODER = True  # Try NVENC/QSV/AMF if available

# FFmpeg settings
# 1. Check bundled resources (for PyInstaller)
# 2. Check next to EXE
# 3. Check system PATH
bundled_ffmpeg = resource_path("ffmpeg.exe")
if os.path.exists(bundled_ffmpeg):
    FFMPEG_PATH = bundled_ffmpeg
elif os.path.exists(os.path.join(EXE_DIR, "ffmpeg.exe")):
    FFMPEG_PATH = os.path.join(EXE_DIR, "ffmpeg.exe")
else:
    FFMPEG_PATH = "ffmpeg"
