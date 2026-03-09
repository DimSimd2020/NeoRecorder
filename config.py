"""
Configuration for NeoRecorder v1.4.8
- User settings with persistence
- Hotkey configuration
- System tray settings
- Screenshot settings
- Overlay settings
"""

import os
import sys
import json
from copy import deepcopy
from typing import Dict, Any

# UI Colors
BG_COLOR = "#09131B"
ACCENT_COLOR = "#27C1F4"
TEXT_COLOR = "#F4FBFF"
SECONDARY_TEXT_COLOR = "#86A2B6"
NEON_BLUE = "#27C1F4"

# App Info
APP_NAME = "NeoRecorder"
VERSION = "1.4.8"
AUTHOR = "DimSimd"


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller"""
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

# User data directory
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "Videos", "NeoRecorder")
SETTINGS_FILE = os.path.join(USER_DATA_DIR, "settings.json")
SCREENSHOTS_DIR = os.path.join(USER_DATA_DIR, "Screenshots")

# Default Settings
DEFAULT_LANG = "ru"
DEFAULT_FORMAT = "mp4"
SCREENSHOT_FORMAT = "png"

# Recording Settings
DEFAULT_FPS = 60
FPS_OPTIONS = [30, 60, 120, 144, 240]

# Quality Presets
QUALITY_PRESETS = {
    "ultrafast": {"crf": 23, "preset": "ultrafast", "label_ru": "Быстрая", "label_en": "Fast"},
    "balanced": {"crf": 20, "preset": "fast", "label_ru": "Баланс", "label_en": "Balanced"},
    "quality": {"crf": 18, "preset": "medium", "label_ru": "Качество", "label_en": "Quality"},
    "lossless": {"crf": 0, "preset": "ultrafast", "label_ru": "Без потерь", "label_en": "Lossless"},
}
DEFAULT_QUALITY = "balanced"

# Hardware Encoder
USE_HARDWARE_ENCODER = True

# FFmpeg path detection
bundled_ffmpeg = resource_path("ffmpeg.exe")
if os.path.exists(bundled_ffmpeg):
    FFMPEG_PATH = bundled_ffmpeg
elif os.path.exists(os.path.join(EXE_DIR, "ffmpeg.exe")):
    FFMPEG_PATH = os.path.join(EXE_DIR, "ffmpeg.exe")
else:
    FFMPEG_PATH = "ffmpeg"

# Default hotkeys
DEFAULT_HOTKEYS = {
    "quick_overlay": "ctrl+shift+s",  # Open quick capture overlay
    "show_window": "ctrl+shift+r",    # Show main window from tray
    "start_recording": "ctrl+shift+f9",
    "stop_recording": "ctrl+shift+f10",
}

# Default user settings
DEFAULT_SETTINGS: Dict[str, Any] = {
    "language": DEFAULT_LANG,
    "fps": DEFAULT_FPS,
    "quality": DEFAULT_QUALITY,
    "output_dir": USER_DATA_DIR,
    "screenshots_dir": SCREENSHOTS_DIR,
    "minimize_to_tray": True,
    "start_minimized": False,
    "start_with_windows": False,
    "hotkeys": deepcopy(DEFAULT_HOTKEYS),
    "last_mode": "screen",
    # Overlay settings
    "overlay_dim_screen": True,
    "overlay_lock_input": True,
}


class Settings:
    """Persistent user settings manager"""
    _instance = None
    _data: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    def _ensure_dirs(self):
        """Create required directories"""
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    
    def _load(self):
        """Load settings from file"""
        self._ensure_dirs()
        self._data = deepcopy(DEFAULT_SETTINGS)
        
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    # Merge with defaults (keeps new keys)
                    for key, value in saved.items():
                        if key in self._data:
                            if isinstance(self._data[key], dict) and isinstance(value, dict):
                                self._data[key].update(value)
                            else:
                                self._data[key] = value
            except Exception as e:
                print(f"Error loading settings: {e}")
    
    def save(self):
        """Save settings to file"""
        self._ensure_dirs()
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def get(self, key: str, default=None):
        """Get setting value"""
        return self._data.get(key, default)
    
    def set(self, key: str, value):
        """Set setting value and save"""
        self._data[key] = value
        self.save()
    
    def get_hotkey(self, action: str) -> str:
        """Get hotkey for action"""
        hotkeys = self._data.get("hotkeys", DEFAULT_HOTKEYS)
        return hotkeys.get(action, DEFAULT_HOTKEYS.get(action, ""))
    
    def set_hotkey(self, action: str, hotkey: str):
        """Set hotkey for action"""
        if "hotkeys" not in self._data:
            self._data["hotkeys"] = deepcopy(DEFAULT_HOTKEYS)
        self._data["hotkeys"][action] = hotkey
        self.save()
    
    @property
    def all(self) -> Dict[str, Any]:
        """Get all settings"""
        return deepcopy(self._data)


# Global settings instance
settings = Settings()
