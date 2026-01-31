"""
Screenshot module for NeoRecorder.
Fast screen capture using Windows API.
"""

import os
import datetime
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple
from PIL import Image
import mss
import mss.tools
from config import SCREENSHOTS_DIR, SCREENSHOT_FORMAT
from utils.logger import get_logger, log_debug


class ScreenshotCapture:
    """
    High-performance screenshot capture.
    Uses mss for fast capture (faster than PIL.ImageGrab).
    """
    
    def __init__(self):
        self._sct = None
        self._output_dir = SCREENSHOTS_DIR
        self._logger = get_logger()
        self._ensure_output_dir()
    
    def _ensure_output_dir(self):
        """Create output directory if needed"""
        os.makedirs(self._output_dir, exist_ok=True)
    
    def _get_mss(self):
        """Get mss instance (lazy init)"""
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct
    
    def capture_fullscreen(self) -> Optional[str]:
        """
        Capture entire primary screen.
        Returns path to saved file or None on error.
        """
        try:
            sct = self._get_mss()
            monitor = sct.monitors[1]  # Primary monitor
            
            screenshot = sct.grab(monitor)
            return self._save_screenshot(screenshot)
            
        except Exception as e:
            self._logger.error(f"Fullscreen capture failed: {e}")
            return None
    
    def capture_region(self, rect: Tuple[int, int, int, int]) -> Optional[str]:
        """
        Capture specific region.
        
        Args:
            rect: (x1, y1, x2, y2) coordinates
        
        Returns:
            Path to saved file or None on error.
        """
        try:
            x1, y1, x2, y2 = rect
            
            # Normalize coordinates
            left = min(x1, x2)
            top = min(y1, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            
            if width < 1 or height < 1:
                return None
            
            sct = self._get_mss()
            monitor = {"left": left, "top": top, "width": width, "height": height}
            
            screenshot = sct.grab(monitor)
            return self._save_screenshot(screenshot)
            
        except Exception as e:
            self._logger.error(f"Region capture failed: {e}")
            return None
    
    def capture_to_clipboard(self, rect: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """
        Capture and copy to clipboard.
        
        Args:
            rect: Optional region, fullscreen if None
        
        Returns:
            True if successful
        """
        try:
            sct = self._get_mss()
            
            if rect:
                x1, y1, x2, y2 = rect
                monitor = {
                    "left": min(x1, x2), 
                    "top": min(y1, y2), 
                    "width": abs(x2 - x1), 
                    "height": abs(y2 - y1)
                }
            else:
                monitor = sct.monitors[1]
            
            screenshot = sct.grab(monitor)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            # Copy to clipboard using Windows API
            self._copy_image_to_clipboard(img)
            
            log_debug("Screenshot copied to clipboard")
            return True
            
        except Exception as e:
            self._logger.error(f"Clipboard capture failed: {e}")
            return False
    
    def _save_screenshot(self, screenshot) -> str:
        """Save screenshot to file"""
        self._ensure_output_dir()
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"Screenshot_{timestamp}.{SCREENSHOT_FORMAT}"
        filepath = os.path.join(self._output_dir, filename)
        
        # Convert and save
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img.save(filepath, optimize=True)
        
        log_debug(f"Screenshot saved: {filepath}")
        return filepath
    
    def _copy_image_to_clipboard(self, image: Image.Image):
        """Copy PIL Image to Windows clipboard"""
        import io
        
        # Convert to BMP format for clipboard
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # Remove BMP header
        output.close()
        
        # Windows clipboard API
        CF_DIB = 8
        GMEM_MOVEABLE = 0x0002
        
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        
        user32.OpenClipboard(None)
        user32.EmptyClipboard()
        
        # Allocate global memory
        hMem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        pMem = kernel32.GlobalLock(hMem)
        ctypes.memmove(pMem, data, len(data))
        kernel32.GlobalUnlock(hMem)
        
        user32.SetClipboardData(CF_DIB, hMem)
        user32.CloseClipboard()
    
    def set_output_dir(self, path: str):
        """Set screenshot output directory"""
        if os.path.isdir(path):
            self._output_dir = path
        else:
            os.makedirs(path, exist_ok=True)
            self._output_dir = path
    
    def get_output_dir(self) -> str:
        """Get current output directory"""
        return self._output_dir
    
    def cleanup(self):
        """Release resources"""
        if self._sct:
            try:
                self._sct.close()
            except:
                pass
            self._sct = None
    
    def __del__(self):
        self.cleanup()


# Global instance
_screenshot_capture: Optional[ScreenshotCapture] = None


def get_screenshot_capture() -> ScreenshotCapture:
    """Get global screenshot capture instance"""
    global _screenshot_capture
    if _screenshot_capture is None:
        _screenshot_capture = ScreenshotCapture()
    return _screenshot_capture
