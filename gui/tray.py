"""
System Tray support for NeoRecorder.
Allows running in background with hotkey support.
"""

import threading
from typing import Callable, Optional
from PIL import Image
import os
from config import ICONS_DIR, APP_NAME
from utils.logger import get_logger


class SystemTray:
    """
    System tray icon with context menu.
    Uses pystray for cross-platform tray support.
    """
    
    def __init__(
        self,
        on_show: Callable,
        on_quick_capture: Callable,
        on_quit: Callable
    ):
        self.on_show = on_show
        self.on_quick_capture = on_quick_capture
        self.on_quit = on_quit
        
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._logger = get_logger()
    
    def start(self):
        """Start system tray icon in background thread"""
        if self._running:
            return
        
        try:
            import pystray
            from pystray import MenuItem, Menu
        except ImportError:
            self._logger.error("pystray not installed")
            return
        
        # Load icon
        icon_path = os.path.join(ICONS_DIR, "rec.png")
        if os.path.exists(icon_path):
            image = Image.open(icon_path)
        else:
            # Fallback: create simple icon
            image = Image.new('RGB', (64, 64), color='#00F2FF')
        
        # Create menu
        menu = Menu(
            MenuItem("Открыть NeoRecorder", self._on_show_click, default=True),
            MenuItem("Быстрый захват", self._on_quick_capture_click),
            Menu.SEPARATOR,
            MenuItem("Выход", self._on_quit_click)
        )
        
        self._icon = pystray.Icon(
            APP_NAME,
            image,
            APP_NAME,
            menu
        )
        
        # Run in thread
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        
        self._logger.info("System tray started")
    
    def _run(self):
        """Run tray icon (blocking)"""
        try:
            self._icon.run()
        except Exception as e:
            self._logger.error(f"Tray error: {e}")
        finally:
            self._running = False
    
    def _on_show_click(self, icon=None, item=None):
        """Handle show click"""
        try:
            self.on_show()
        except Exception as e:
            self._logger.error(f"Show callback error: {e}")
    
    def _on_quick_capture_click(self, icon=None, item=None):
        """Handle quick capture click"""
        try:
            self.on_quick_capture()
        except Exception as e:
            self._logger.error(f"Quick capture callback error: {e}")
    
    def _on_quit_click(self, icon=None, item=None):
        """Handle quit click"""
        self.stop()
        try:
            self.on_quit()
        except Exception as e:
            self._logger.error(f"Quit callback error: {e}")
    
    def stop(self):
        """Stop tray icon"""
        if self._icon:
            try:
                self._icon.stop()
            except:
                pass
            self._icon = None
        self._running = False
    
    def update_icon(self, icon_name: str):
        """Update tray icon"""
        if not self._icon:
            return
        
        icon_path = os.path.join(ICONS_DIR, icon_name)
        if os.path.exists(icon_path):
            try:
                self._icon.icon = Image.open(icon_path)
            except:
                pass
    
    def notify(self, title: str, message: str):
        """Show tray notification"""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except:
                pass
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    def __del__(self):
        self.stop()
