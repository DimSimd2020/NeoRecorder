"""
Custom Toast notifications for NeoRecorder.
Fixed DPI scaling, proper text wrapping, correct positioning.
"""

import tkinter as tk
import ctypes


class NeoToast:
    """Beautiful toast notification with proper DPI and text wrapping"""
    
    _active_toast = None
    
    @classmethod
    def show(cls, title: str, message: str, icon: str = "📷", duration: float = 4.0):
        """Show toast notification"""
        
        # Close existing toast
        if cls._active_toast:
            try:
                cls._active_toast.destroy()
            except:
                pass
            cls._active_toast = None
        
        # Create hidden root if needed (for Toplevel to work without main window)
        try:
            root = tk._default_root
            if root is None:
                root = tk.Tk()
                root.withdraw()
        except:
            root = tk.Tk()
            root.withdraw()
        
        # Create toast window
        toast = tk.Toplevel()
        cls._active_toast = toast
        
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.attributes("-alpha", 0.0)
        toast.configure(bg="#1F1F1F")
        
        # Get DPI scale - use winfo_fpixels which accounts for DPI
        try:
            scale = toast.winfo_fpixels('1i') / 96.0
        except:
            scale = 1.0
        
        # Cap scale to reasonable values
        scale = max(1.0, min(scale, 2.5))
        
        # Dimensions scaled for DPI
        base_width = 340
        base_height = 90
        
        width = int(base_width * scale)
        height = int(base_height * scale)
        
        # Get ACTUAL screen size (physical pixels)
        # winfo_screenwidth/height return logical pixels when DPI aware
        # We need to use ctypes to get real physical screen size
        try:
            user32 = ctypes.windll.user32
            # SM_CXSCREEN = 0, SM_CYSCREEN = 1
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
        except:
            screen_w = toast.winfo_screenwidth()
            screen_h = toast.winfo_screenheight()
        
        # Position in bottom-right corner (physical pixels)
        pad_x = int(25 * scale)
        pad_y = int(80 * scale)  # Above taskbar
        
        x = screen_w - width - pad_x
        y = screen_h - height - pad_y
        
        toast.geometry(f"{width}x{height}+{x}+{y}")
        
        # Main frame with border
        frame = tk.Frame(
            toast, 
            bg="#252525",
            highlightbackground="#00F2FF",
            highlightthickness=2
        )
        frame.pack(fill="both", expand=True)
        
        # Content frame with padding
        content = tk.Frame(frame, bg="#252525")
        content.pack(fill="both", expand=True, padx=int(12 * scale), pady=int(10 * scale))
        
        # Icon
        icon_font_size = max(16, int(18 * scale))
        icon_lbl = tk.Label(
            content, 
            text=icon, 
            font=("Segoe UI Emoji", icon_font_size),
            bg="#252525",
            fg="white"
        )
        icon_lbl.pack(side="left", padx=(0, int(12 * scale)))
        
        # Text container
        text_frame = tk.Frame(content, bg="#252525")
        text_frame.pack(side="left", fill="both", expand=True)
        
        # Title
        title_font_size = max(10, int(10 * scale))
        title_lbl = tk.Label(
            text_frame,
            text=title,
            font=("Segoe UI", title_font_size, "bold"),
            bg="#252525",
            fg="#00F2FF",
            anchor="w"
        )
        title_lbl.pack(fill="x", anchor="w")
        
        # Message with proper wrapping
        msg_font_size = max(9, int(9 * scale))
        wrap_width = int((base_width - 80) * scale)  # Account for icon and padding
        
        msg_lbl = tk.Label(
            text_frame,
            text=message,
            font=("Segoe UI", msg_font_size),
            bg="#252525",
            fg="#CCCCCC",
            anchor="w",
            justify="left",
            wraplength=wrap_width
        )
        msg_lbl.pack(fill="x", anchor="w", pady=(int(4 * scale), 0))
        
        # Close on click
        def on_click(e=None):
            try:
                toast.destroy()
                cls._active_toast = None
            except:
                pass
        
        for w in [toast, frame, content, icon_lbl, text_frame, title_lbl, msg_lbl]:
            w.bind("<Button-1>", on_click)
        
        # Fade in animation
        def fade_in(alpha=0.0):
            try:
                if not toast.winfo_exists():
                    return
                if alpha < 0.95:
                    toast.attributes("-alpha", alpha)
                    toast.after(20, lambda: fade_in(alpha + 0.12))
                else:
                    toast.attributes("-alpha", 0.95)
            except:
                pass
        
        # Fade out animation
        def fade_out(alpha=0.95):
            try:
                if not toast.winfo_exists():
                    return
                if alpha > 0.0:
                    toast.attributes("-alpha", alpha)
                    toast.after(25, lambda: fade_out(alpha - 0.1))
                else:
                    toast.destroy()
                    cls._active_toast = None
            except:
                pass
        
        fade_in()
        toast.after(int(duration * 1000), fade_out)


def show_recording_complete(title: str, message: str):
    """Show recording complete notification"""
    NeoToast.show(title, message, icon="✅", duration=5.0)


def show_simple_notification(title: str, message: str):
    """Show simple notification"""
    NeoToast.show(title, message, icon="📷", duration=4.0)


def show_error_notification(title: str, message: str):
    """Show error notification"""
    NeoToast.show(title, message, icon="❌", duration=5.0)


def show_warning_notification(title: str, message: str):
    """Show warning notification"""
    NeoToast.show(title, message, icon="⚠️", duration=6.0)
