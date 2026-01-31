"""
Custom Toast notifications for NeoRecorder.
Compact, DPI-aware dark notifications.
"""

import tkinter as tk
import ctypes


def enable_dpi_awareness():
    """Enable DPI awareness for proper scaling"""
    try:
        # Try to set per-monitor DPI awareness
        ctypes.windll.shcore.SetProcessDpiAwareness(1) 
    except:
        pass


class NeoToast:
    """Beautiful compact toast notification"""
    
    _active_toast = None
    
    @classmethod
    def show(cls, title: str, message: str, icon: str = "📷", duration: float = 3.5):
        """Show toast notification"""
        enable_dpi_awareness()
        
        # Close existing toast
        if cls._active_toast:
            try:
                cls._active_toast.destroy()
            except:
                pass
        
        # Create toast window
        toast = tk.Toplevel()
        cls._active_toast = toast
        
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.attributes("-alpha", 0.0)
        toast.configure(bg="#1F1F1F")
        
        # DPI Scaling calculation
        try:
            dpi = toast.winfo_fpixels('1i')
            scale = dpi / 96.0
        except:
            scale = 1.0
            
        # Limit scale to reasonable values to prevent huge UI
        scale = min(scale, 2.0)
        
        # Compact dimensions
        base_w = 280
        base_h = 60
        
        width = int(base_w * scale)
        height = int(base_h * scale)
        
        screen_w = toast.winfo_screenwidth()
        screen_h = toast.winfo_screenheight()
        
        # Padding from edges
        pad_x = int(20 * scale)
        pad_y = int(80 * scale) # Above taskbar
        
        x = screen_w - width - pad_x
        y = screen_h - height - pad_y
        
        toast.geometry(f"{width}x{height}+{x}+{y}")
        
        # Main frame
        frame = tk.Frame(
            toast, 
            bg="#252525",
            highlightbackground="#00F2FF",
            highlightthickness=1
        )
        frame.pack(fill="both", expand=True)
        
        # Icon area
        icon_size = int(18 * scale)
        icon_frame = tk.Frame(frame, bg="#252525", width=int(50*scale))
        icon_frame.pack(side="left", fill="y", padx=(int(10*scale), int(5*scale)))
        
        icon_lbl = tk.Label(
            icon_frame, 
            text=icon, 
            font=("Segoe UI Emoji", icon_size),
            bg="#252525",
            fg="white"
        )
        icon_lbl.place(relx=0.5, rely=0.5, anchor="center")
        
        # Text container
        text_frame = tk.Frame(frame, bg="#252525")
        text_frame.pack(side="left", fill="both", expand=True, padx=int(5 * scale), pady=int(8 * scale))
        
        # Title
        title_size = int(10 * scale)
        title_lbl = tk.Label(
            text_frame,
            text=title,
            font=("Segoe UI", title_size, "bold"),
            bg="#252525",
            fg="#00F2FF",
            anchor="w"
        )
        title_lbl.pack(fill="x")
        
        # Message
        msg_size = int(9 * scale)
        # Truncate long messages
        if len(message) > 40:
            message = message[:37] + "..."
            
        msg_lbl = tk.Label(
            text_frame,
            text=message,
            font=("Segoe UI", msg_size),
            bg="#252525",
            fg="#DDDDDD",
            anchor="w"
        )
        msg_lbl.pack(fill="x")
        
        # Close on click
        def on_click(e=None):
            try:
                toast.destroy()
            except:
                pass
        
        for w in [toast, frame, icon_lbl, text_frame, title_lbl, msg_lbl]:
            w.bind("<Button-1>", on_click)
        
        # Animation
        def fade_in(alpha=0.0):
            try:
                if alpha < 0.95:
                    toast.attributes("-alpha", alpha)
                    toast.after(15, lambda: fade_in(alpha + 0.15))
                else:
                    toast.attributes("-alpha", 0.95)
            except:
                pass
        
        def fade_out(alpha=0.95):
            try:
                if alpha > 0.0:
                    toast.attributes("-alpha", alpha)
                    toast.after(30, lambda: fade_out(alpha - 0.1))
                else:
                    toast.destroy()
            except:
                pass
        
        fade_in()
        toast.after(int(duration * 1000), fade_out)


def show_recording_complete(title_or_filename, message_or_path, path_or_action=None):
    """Show notification"""
    if path_or_action:
        title = "NeoRecorder"
        message = f"{title_or_filename}"
    else:
        title = str(title_or_filename)
        message = str(message_or_path)
    
    NeoToast.show(title, message, icon="✅")


def show_simple_notification(title: str, message: str):
    """Show simple notification"""
    NeoToast.show(title, message, icon="📷")
