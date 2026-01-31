"""
Toast notification popup for NeoRecorder.
Custom tkinter-based toast that works everywhere.
"""

import tkinter as tk
from typing import Optional
import threading


class ToastNotification:
    """Simple toast notification popup"""
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def show(cls, master, title: str, message: str, duration: int = 3000):
        """Show toast notification"""
        # Run in main thread
        if master:
            master.after(0, lambda: cls._show_toast(master, title, message, duration))
    
    @classmethod
    def _show_toast(cls, master, title: str, message: str, duration: int):
        """Create and show toast window"""
        with cls._lock:
            # Close previous toast
            if cls._instance:
                try:
                    cls._instance.destroy()
                except:
                    pass
            
            toast = tk.Toplevel(master)
            cls._instance = toast
            
            # Window setup
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)
            toast.configure(bg="#1E1E1E")
            
            # Size and position (bottom-right corner)
            width = 320
            height = 80
            screen_w = toast.winfo_screenwidth()
            screen_h = toast.winfo_screenheight()
            x = screen_w - width - 20
            y = screen_h - height - 60  # Above taskbar
            toast.geometry(f"{width}x{height}+{x}+{y}")
            
            # Frame with border
            frame = tk.Frame(toast, bg="#2D2D2D", highlightbackground="#00F2FF", highlightthickness=1)
            frame.pack(fill="both", expand=True, padx=2, pady=2)
            
            # Icon
            icon_label = tk.Label(frame, text="📷", font=("Segoe UI Emoji", 24), bg="#2D2D2D", fg="white")
            icon_label.pack(side="left", padx=10)
            
            # Text container
            text_frame = tk.Frame(frame, bg="#2D2D2D")
            text_frame.pack(side="left", fill="both", expand=True, padx=5, pady=8)
            
            # Title
            title_label = tk.Label(
                text_frame, 
                text=title, 
                font=("Segoe UI", 11, "bold"), 
                bg="#2D2D2D", 
                fg="#00F2FF",
                anchor="w"
            )
            title_label.pack(fill="x")
            
            # Message (truncate if too long)
            msg_text = message.replace('\n', ' ')
            if len(msg_text) > 45:
                msg_text = msg_text[:42] + "..."
            
            msg_label = tk.Label(
                text_frame, 
                text=msg_text, 
                font=("Segoe UI", 9), 
                bg="#2D2D2D", 
                fg="#CCCCCC",
                anchor="w"
            )
            msg_label.pack(fill="x")
            
            # Click to close
            def close_toast(e=None):
                try:
                    toast.destroy()
                except:
                    pass
            
            toast.bind("<Button-1>", close_toast)
            frame.bind("<Button-1>", close_toast)
            
            # Fade in effect (optional)
            toast.attributes("-alpha", 0.0)
            
            def fade_in(alpha=0.0):
                if alpha < 0.95:
                    toast.attributes("-alpha", alpha)
                    toast.after(20, lambda: fade_in(alpha + 0.1))
                else:
                    toast.attributes("-alpha", 0.95)
            
            fade_in()
            
            # Auto close after duration
            def auto_close():
                try:
                    # Fade out
                    def fade_out(alpha=0.95):
                        if alpha > 0.1:
                            toast.attributes("-alpha", alpha)
                            toast.after(30, lambda: fade_out(alpha - 0.15))
                        else:
                            toast.destroy()
                    fade_out()
                except:
                    pass
            
            toast.after(duration, auto_close)


def show_toast(master, title: str, message: str, duration: int = 3000):
    """Convenience function to show toast"""
    ToastNotification.show(master, title, message, duration)
