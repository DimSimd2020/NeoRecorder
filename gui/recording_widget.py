
"""
Recording Widget - Floating overlay showing recording status.
Hidden from screen capture, always on top, draggable.
"""

import customtkinter as ctk
import time
import ctypes
from typing import Callable, Optional
from config import NEON_BLUE, BG_COLOR

# Windows Constants for transparency and exclusion
WDA_EXCLUDEFROMCAPTURE = 0x00000011

class RecordingWidget(ctk.CTkToplevel):
    def __init__(self, parent, on_stop: Callable, on_pause: Callable, 
                 get_elapsed: Optional[Callable[[], float]] = None):
        super().__init__(parent)
        self.on_stop = on_stop
        self.on_pause = on_pause
        self.get_elapsed = get_elapsed  # Function to get accurate elapsed time from recorder
        
        # Transparent, no borders, always on top
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry("220x50+100+100")  # Start position
        self.configure(fg_color="#1A1A1A")
        
        # Hide from capture
        self.set_exclusion()
        
        self.setup_ui()
        
        # Draggable logic
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)
        
        # State
        self.start_time = time.time()
        self.is_paused = False
        self._pause_flash = False
        self._update_id = None
        
        self.update_timer()

    def set_exclusion(self):
        """Exclude window from screen capture (Windows 10 2004+)"""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception as e:
            print(f"Exclusion failed: {e}")

    def setup_ui(self):
        self.frame = ctk.CTkFrame(
            self, 
            fg_color="#1A1A1A", 
            corner_radius=10, 
            border_width=2, 
            border_color=NEON_BLUE
        )
        self.frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Recording indicator (pulsing dot)
        self.rec_indicator = ctk.CTkLabel(
            self.frame, 
            text="●", 
            font=("Arial", 16), 
            text_color="#FF3333",
            width=20
        )
        self.rec_indicator.pack(side="left", padx=(10, 5))
        
        # Timer
        self.time_label = ctk.CTkLabel(
            self.frame, 
            text="00:00", 
            font=("Consolas", 18, "bold"), 
            text_color="white"
        )
        self.time_label.pack(side="left", padx=5)
        
        # Pause button
        self.pause_btn = ctk.CTkButton(
            self.frame, 
            text="⏸", 
            width=35, 
            height=35, 
            font=("Arial", 14),
            fg_color="transparent", 
            hover_color="#333333", 
            command=self.toggle_pause
        )
        self.pause_btn.pack(side="left", padx=2)
        
        # Stop button
        self.stop_btn = ctk.CTkButton(
            self.frame, 
            text="⏹", 
            width=35, 
            height=35, 
            font=("Arial", 14),
            fg_color="transparent", 
            hover_color="#CC0000", 
            text_color="#FF3333", 
            command=self._on_stop_click
        )
        self.stop_btn.pack(side="left", padx=5)
        
        # Animate recording indicator
        self._animate_indicator()

    def _animate_indicator(self):
        """Pulsing recording indicator"""
        if not self.winfo_exists():
            return
            
        if self.is_paused:
            self.rec_indicator.configure(text_color="#888888")
            self._pause_flash = not self._pause_flash
            if self._pause_flash:
                self.rec_indicator.configure(text="●")
            else:
                self.rec_indicator.configure(text="○")
        else:
            self.rec_indicator.configure(text="●", text_color="#FF3333")
        
        self.after(500, self._animate_indicator)

    def toggle_pause(self):
        """Toggle pause state and call callback"""
        self.is_paused = self.on_pause(not self.is_paused)
        self.pause_btn.configure(text="▶" if self.is_paused else "⏸")
        
        if self.is_paused:
            self.frame.configure(border_color="#888888")
            self.time_label.configure(text_color="#888888")
        else:
            self.frame.configure(border_color=NEON_BLUE)
            self.time_label.configure(text_color="white")

    def _on_stop_click(self):
        """Handle stop button click"""
        if self._update_id:
            self.after_cancel(self._update_id)
            self._update_id = None
        self.on_stop()

    def update_timer(self):
        """Update timer display"""
        if not self.winfo_exists():
            return
        
        # Get elapsed time from recorder if available (more accurate)
        if self.get_elapsed:
            elapsed = self.get_elapsed()
        else:
            elapsed = time.time() - self.start_time
        
        elapsed = int(elapsed)
        hours, remainder = divmod(elapsed, 3600)
        mins, secs = divmod(remainder, 60)
        
        if hours > 0:
            self.time_label.configure(text=f"{hours:01d}:{mins:02d}:{secs:02d}")
        else:
            self.time_label.configure(text=f"{mins:02d}:{secs:02d}")
        
        self._update_id = self.after(100, self.update_timer)  # Update more frequently for accuracy

    def set_paused(self, paused: bool):
        """Set pause state externally"""
        if paused != self.is_paused:
            self.is_paused = paused
            self.pause_btn.configure(text="▶" if paused else "⏸")
            
            if paused:
                self.frame.configure(border_color="#888888")
                self.time_label.configure(text_color="#888888")
            else:
                self.frame.configure(border_color=NEON_BLUE)
                self.time_label.configure(text_color="white")

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def destroy(self):
        """Clean up before destroying"""
        if self._update_id:
            self.after_cancel(self._update_id)
        super().destroy()
