
import win32gui
import win32process
import psutil

class WindowFinder:
    @staticmethod
    def get_active_windows():
        windows = []
        
        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                title = win32gui.GetWindowText(hwnd)
                # Filter out some common system windows if necessary
                if title not in ["Program Manager", "Settings"]:
                    windows.append({
                        'hwnd': hwnd,
                        'title': title
                    })
        
        win32gui.EnumWindows(enum_handler, None)
        return windows

    @staticmethod
    def get_window_rect(hwnd):
        try:
            return win32gui.GetWindowRect(hwnd)
        except Exception:
            return None
