
"""Windows notification support for NeoRecorder"""

import os
import threading

def show_recording_complete(title_or_filename, message_or_path, path_or_action=None):
    """
    Show Windows notification.
    
    Overloaded:
    1. show_recording_complete(filename, path, duration) -> Legacy video recording
    2. show_recording_complete(title, message, open_path) -> Generic notification
    """
    
    # Determine arguments
    if path_or_action and os.path.exists(str(message_or_path)):
        # Legacy: filename, path, duration
        filename = title_or_filename
        path = message_or_path
        duration = path_or_action
        
        title = "NeoRecorder"
        message = f"{filename}\n{duration}"
        click_path = path
    else:
        # Generic: title, message, open_path
        title = title_or_filename
        message = message_or_path
        click_path = path_or_action
    
    # Run in thread to not block UI
    threading.Thread(target=_show_toast, args=(title, message, click_path), daemon=True).start()

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
