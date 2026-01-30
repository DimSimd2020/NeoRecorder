
import customtkinter as ctk
import time
import ctypes
from config import NEON_BLUE, BG_COLOR

# Windows Constants for transparency and exclusion
WDA_EXCLUDEFROMCAPTURE = 0x00000011

class RecordingWidget(ctk.CTkToplevel):
    def __init__(self, parent, on_stop, on_pause):
        super().__init__(parent)
        self.on_stop = on_stop
        self.on_pause = on_pause
        
        # Transparent, no borders, always on top
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry("200x50+100+100") # Start position
        self.configure(fg_color="#1A1A1A")
        
        # Hide from capture
        self.set_exclusion()
        
        self.setup_ui()
        
        # Draggable logic
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)
        
        self.start_time = time.time()
        self.paused_time = 0
        self.is_paused = False
        self.update_timer()

    def set_exclusion(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            # For Windows 10 version 2004 and newer
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception as e:
            print(f"Exclusion failed: {e}")

    def setup_ui(self):
        self.frame = ctk.CTkFrame(self, fg_color="#1A1A1A", corner_radius=10, border_width=1, border_color=NEON_BLUE)
        self.frame.pack(fill="both", expand=True)
        
        self.time_label = ctk.CTkLabel(self.frame, text="00:00", font=("Consolas", 16, "bold"), text_color="white")
        self.time_label.pack(side="left", padx=10)
        
        self.pause_btn = ctk.CTkButton(self.frame, text="⏸", width=30, height=30, fg_color="transparent", 
                                       hover_color="#333333", command=self.toggle_pause)
        self.pause_btn.pack(side="left", padx=2)
        
        self.stop_btn = ctk.CTkButton(self.frame, text="⏹", width=30, height=30, fg_color="transparent", 
                                      hover_color="#CC0000", text_color="#FF3333", command=self.on_stop)
        self.stop_btn.pack(side="left", padx=5)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_btn.configure(text="▶" if self.is_paused else "⏸")
        self.on_pause(self.is_paused)

    def update_timer(self):
        if not self.is_paused:
            elapsed = int(time.time() - self.start_time)
            mins, secs = divmod(elapsed, 60)
            self.time_label.configure(text=f"{mins:02d}:{secs:02d}")
        self.after(1000, self.update_timer)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")
