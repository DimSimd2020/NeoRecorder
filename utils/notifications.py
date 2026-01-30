
"""Windows notification support for NeoRecorder"""

import os
import threading

def show_recording_complete(filename, path, duration):
    """
    Show Windows notification when recording is complete.
    
    Args:
        filename: Name of the saved file
        path: Directory where file was saved
        duration: Duration string (e.g., "05:32")
    """
    title = "NeoRecorder"
    message = f"{filename} сохранено в {path}.\nДлительность записи: {duration}"
    
    # Run in thread to not block UI
    threading.Thread(target=_show_toast, args=(title, message, path), daemon=True).start()

def _show_toast(title, message, path):
    """Internal function to show toast notification"""
    try:
        # Try winotify first (modern, reliable)
        try:
            from winotify import Notification, audio
            toast = Notification(
                app_id="NeoRecorder",
                title=title,
                msg=message,
                duration="short"
            )
            toast.set_audio(audio.Default, loop=False)
            
            # Add action to open folder
            toast.add_actions(label="Открыть папку", launch=f"explorer \"{path}\"")
            
            toast.show()
            return
        except ImportError:
            pass
        
        # Fallback to win10toast
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(
                title,
                message,
                duration=5,
                threaded=False
            )
            return
        except ImportError:
            pass
        
        # Fallback to plyer
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                timeout=5
            )
            return
        except ImportError:
            pass
        
        # Ultimate fallback: Windows message box
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
        
    except Exception as e:
        print(f"Notification error: {e}")

def install_notification_dependencies():
    """Install notification library if not present"""
    import subprocess
    import sys
    
    try:
        import winotify
    except ImportError:
        print("Installing winotify for notifications...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "winotify"])
