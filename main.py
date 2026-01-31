"""
NeoRecorder - Main Entry Point
With Single Instance enforcement via Windows Mutex
"""

import sys
import ctypes
from ctypes import wintypes

# === SINGLE INSTANCE CHECK ===
# Using Windows Mutex to ensure only one instance runs

MUTEX_NAME = "NeoRecorder_SingleInstance_Mutex"

def is_already_running():
    """Check if another instance is already running using Windows Mutex"""
    kernel32 = ctypes.windll.kernel32
    
    # Try to create mutex
    handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    last_error = kernel32.GetLastError()
    
    # ERROR_ALREADY_EXISTS = 183
    if last_error == 183:
        kernel32.CloseHandle(handle)
        return True
    
    # Keep mutex alive (don't close it)
    return False

def focus_existing_window():
    """Try to bring existing NeoRecorder window to front"""
    user32 = ctypes.windll.user32
    
    # Find window by title
    hwnd = user32.FindWindowW(None, "NeoRecorder")
    if hwnd:
        # SW_RESTORE = 9, SW_SHOW = 5
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        return True
    return False

# Check single instance BEFORE importing heavy modules
if is_already_running():
    focus_existing_window()
    sys.exit(0)

# === DPI AWARENESS ===
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

# === IMPORT APP ===
from gui.app import NeoRecorderApp

if __name__ == "__main__":
    app = NeoRecorderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
