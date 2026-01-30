
from gui.app import NeoRecorderApp

import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

if __name__ == "__main__":
    app = NeoRecorderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
