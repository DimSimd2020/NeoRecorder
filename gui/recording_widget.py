"""
Recording Widget v1.3.0 - Floating overlay showing recording status.
- Real-time progress display (FPS, bitrate, dropped frames)
- Pause state indication
- Hidden from screen capture
"""

import customtkinter as ctk
import time
import ctypes
from typing import Callable, Optional
from config import NEON_BLUE, BG_COLOR

# Windows Constants for exclusion from capture
WDA_EXCLUDEFROMCAPTURE = 0x00000011


class RecordingWidget(ctk.CTkToplevel):
    def __init__(self, parent, on_stop: Callable, on_pause: Callable,
                 get_elapsed: Optional[Callable[[], float]] = None,
                 get_progress: Optional[Callable] = None):
        super().__init__(parent)
        self.on_stop = on_stop
        self.on_pause = on_pause
        self.get_elapsed = get_elapsed
        self.get_progress = get_progress  # Function to get RecordingProgress
        
        # Window setup
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry("280x70+100+100")
        self.configure(fg_color="#1A1A1A")
        
        # Hide from capture
        self.set_exclusion()
        
        self.setup_ui()
        
        # Draggable
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)
        
        # State
        self.is_paused = False
        self._pause_flash = False
        self._update_id = None
        self._progress_id = None
        
        # Start updates
        self.update_timer()
        self.update_progress()

    def set_exclusion(self):
        """Exclude window from screen capture (Windows 10 2004+)"""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception as e:
            print(f"Capture exclusion failed: {e}")

    def setup_ui(self):
        self.frame = ctk.CTkFrame(
            self,
            fg_color="#1A1A1A",
            corner_radius=10,
            border_width=2,
            border_color=NEON_BLUE
        )
        self.frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Top row: indicator + timer + buttons
        self.top_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.top_row.pack(fill="x", padx=5, pady=(5, 2))
        
        # Recording indicator
        self.rec_indicator = ctk.CTkLabel(
            self.top_row,
            text="●",
            font=("Arial", 16),
            text_color="#FF3333",
            width=20
        )
        self.rec_indicator.pack(side="left", padx=(5, 5))
        
        # Timer
        self.time_label = ctk.CTkLabel(
            self.top_row,
            text="00:00",
            font=("Consolas", 18, "bold"),
            text_color="white"
        )
        self.time_label.pack(side="left", padx=5)
        
        # Pause button
        self.pause_btn = ctk.CTkButton(
            self.top_row,
            text="⏸",
            width=35,
            height=30,
            font=("Arial", 14),
            fg_color="transparent",
            hover_color="#333333",
            command=self.toggle_pause
        )
        self.pause_btn.pack(side="right", padx=2)
        
        # Stop button
        self.stop_btn = ctk.CTkButton(
            self.top_row,
            text="⏹",
            width=35,
            height=30,
            font=("Arial", 14),
            fg_color="transparent",
            hover_color="#CC0000",
            text_color="#FF3333",
            command=self._on_stop_click
        )
        self.stop_btn.pack(side="right", padx=2)
        
        # Bottom row: progress info (FPS, bitrate, dropped)
        self.bottom_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.bottom_row.pack(fill="x", padx=10, pady=(0, 5))
        
        self.fps_label = ctk.CTkLabel(
            self.bottom_row,
            text="FPS: --",
            font=("Consolas", 10),
            text_color="#888888"
        )
        self.fps_label.pack(side="left", padx=5)
        
        self.bitrate_label = ctk.CTkLabel(
            self.bottom_row,
            text="Bitrate: --",
            font=("Consolas", 10),
            text_color="#888888"
        )
        self.bitrate_label.pack(side="left", padx=10)
        
        self.dropped_label = ctk.CTkLabel(
            self.bottom_row,
            text="",
            font=("Consolas", 10),
            text_color="#FF6666"
        )
        self.dropped_label.pack(side="right", padx=5)
        
        # Start indicator animation
        self._animate_indicator()

    def _animate_indicator(self):
        """Pulsing recording indicator"""
        if not self.winfo_exists():
            return
        
        if self.is_paused:
            self.rec_indicator.configure(text_color="#888888")
            self._pause_flash = not self._pause_flash
            self.rec_indicator.configure(text="●" if self._pause_flash else "○")
        else:
            self.rec_indicator.configure(text="●", text_color="#FF3333")
        
        self.after(500, self._animate_indicator)

    def toggle_pause(self):
        """Toggle pause and update visuals"""
        new_state = self.on_pause(not self.is_paused)
        self.set_paused(new_state)

    def set_paused(self, paused: bool):
        """Update pause state and visuals"""
        self.is_paused = paused
        self.pause_btn.configure(text="▶" if paused else "⏸")
        
        if paused:
            self.frame.configure(border_color="#888888")
            self.time_label.configure(text_color="#888888")
            self.fps_label.configure(text="FPS: PAUSED")
        else:
            self.frame.configure(border_color=NEON_BLUE)
            self.time_label.configure(text_color="white")

    def _on_stop_click(self):
        """Handle stop button"""
        self._cancel_updates()
        self.on_stop()

    def _cancel_updates(self):
        """Cancel all scheduled updates"""
        if self._update_id:
            self.after_cancel(self._update_id)
            self._update_id = None
        if self._progress_id:
            self.after_cancel(self._progress_id)
            self._progress_id = None

    def update_timer(self):
        """Update timer display"""
        if not self.winfo_exists():
            return
        
        if self.get_elapsed:
            elapsed = self.get_elapsed()
        else:
            elapsed = 0
        
        elapsed = int(elapsed)
        hours, remainder = divmod(elapsed, 3600)
        mins, secs = divmod(remainder, 60)
        
        if hours > 0:
            self.time_label.configure(text=f"{hours:01d}:{mins:02d}:{secs:02d}")
        else:
            self.time_label.configure(text=f"{mins:02d}:{secs:02d}")
        
        self._update_id = self.after(100, self.update_timer)

    def update_progress(self):
        """Update progress display (FPS, bitrate, dropped)"""
        if not self.winfo_exists():
            return
        
        if self.get_progress and not self.is_paused:
            try:
                progress = self.get_progress()
                
                # FPS
                fps_text = f"FPS: {progress.fps:.0f}" if progress.fps > 0 else "FPS: --"
                self.fps_label.configure(text=fps_text)
                
                # Color FPS based on performance
                if progress.fps > 0:
                    expected_fps = 60  # Could get from settings
                    if progress.fps >= expected_fps * 0.95:
                        self.fps_label.configure(text_color="#00FF00")  # Green
                    elif progress.fps >= expected_fps * 0.8:
                        self.fps_label.configure(text_color="#FFAA00")  # Yellow
                    else:
                        self.fps_label.configure(text_color="#FF6666")  # Red
                
                # Bitrate
                bitrate_text = f"Bitrate: {progress.bitrate}"
                self.bitrate_label.configure(text=bitrate_text)
                
                # Dropped frames warning
                if progress.dropped > 0:
                    self.dropped_label.configure(text=f"Dropped: {progress.dropped}")
                else:
                    self.dropped_label.configure(text="")
                    
            except Exception as e:
                print(f"Progress update error: {e}")
        
        self._progress_id = self.after(500, self.update_progress)

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
        self._cancel_updates()
        super().destroy()
