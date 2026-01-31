"""
Quick Capture Overlay for NeoRecorder.
Floating toolbar with Screenshot/Recording modes (like Windows Snipping Tool).
"""

import customtkinter as ctk
import tkinter as tk
from typing import Callable, Optional, Tuple
import ctypes
from PIL import Image
from config import NEON_BLUE, BG_COLOR, ICONS_DIR
import os

# Windows constants
WDA_EXCLUDEFROMCAPTURE = 0x00000011


class QuickOverlay(ctk.CTkToplevel):
    """
    Quick capture overlay - floating toolbar with mode selection.
    Similar to Windows 11 Snipping Tool.
    """
    
    def __init__(
        self, 
        on_screenshot: Callable[[Tuple[int, int, int, int]], None],
        on_record: Callable[[Tuple[int, int, int, int]], None],
        on_close: Optional[Callable] = None
    ):
        super().__init__()
        
        self.on_screenshot = on_screenshot
        self.on_record = on_record
        self.on_close = on_close
        
        # Window setup
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color="#1A1A1A")
        
        # Center at top of screen
        screen_width = self.winfo_screenwidth()
        toolbar_width = 320
        toolbar_height = 50
        x = (screen_width - toolbar_width) // 2
        y = 30
        self.geometry(f"{toolbar_width}x{toolbar_height}+{x}+{y}")
        
        # Current mode: "screenshot" or "record"
        self.current_mode = "screenshot"
        self.selection_overlay = None
        
        self._setup_ui()
        self._set_exclusion()
        
        # Make draggable
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._do_drag)
        
        # ESC to close
        self.bind("<Escape>", lambda e: self._close())
        self.focus_force()
    
    def _set_exclusion(self):
        """Exclude from screen capture"""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except:
            pass
    
    def _setup_ui(self):
        """Create toolbar UI"""
        self.frame = ctk.CTkFrame(
            self,
            fg_color="#2D2D2D",
            corner_radius=12,
            border_width=1,
            border_color="#444444"
        )
        self.frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Left side: mode buttons
        self.modes_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.modes_frame.pack(side="left", padx=10, pady=5)
        
        # Screenshot mode button
        self.screenshot_btn = ctk.CTkButton(
            self.modes_frame,
            text="📷",
            width=40,
            height=36,
            font=("Segoe UI Emoji", 18),
            fg_color=NEON_BLUE,
            hover_color="#00C8D4",
            corner_radius=8,
            command=lambda: self._set_mode("screenshot")
        )
        self.screenshot_btn.pack(side="left", padx=2)
        
        # Record mode button
        self.record_btn = ctk.CTkButton(
            self.modes_frame,
            text="🎬",
            width=40,
            height=36,
            font=("Segoe UI Emoji", 18),
            fg_color="transparent",
            hover_color="#444444",
            corner_radius=8,
            command=lambda: self._set_mode("record")
        )
        self.record_btn.pack(side="left", padx=2)
        
        # Separator
        separator = ctk.CTkFrame(self.frame, width=1, height=30, fg_color="#555555")
        separator.pack(side="left", padx=10)
        
        # Region selection button (main action)
        self.select_btn = ctk.CTkButton(
            self.frame,
            text="⬚ Выбрать область",
            width=130,
            height=36,
            font=("Segoe UI", 12),
            fg_color="#444444",
            hover_color="#555555",
            corner_radius=8,
            command=self._start_selection
        )
        self.select_btn.pack(side="left", padx=5)
        
        # Close button
        self.close_btn = ctk.CTkButton(
            self.frame,
            text="✕",
            width=36,
            height=36,
            font=("Arial", 14),
            fg_color="transparent",
            hover_color="#FF4444",
            text_color="#888888",
            corner_radius=8,
            command=self._close
        )
        self.close_btn.pack(side="right", padx=5)
    
    def _set_mode(self, mode: str):
        """Set capture mode"""
        self.current_mode = mode
        
        if mode == "screenshot":
            self.screenshot_btn.configure(fg_color=NEON_BLUE)
            self.record_btn.configure(fg_color="transparent")
            self.select_btn.configure(text="⬚ Снимок области")
        else:
            self.screenshot_btn.configure(fg_color="transparent")
            self.record_btn.configure(fg_color="#FF4444")
            self.select_btn.configure(text="⬚ Запись области")
    
    def _start_selection(self):
        """Start region selection"""
        # Hide toolbar during selection
        self.withdraw()
        
        # Create fullscreen selection overlay
        self.selection_overlay = SelectionOverlay(
            on_select=self._on_region_selected,
            on_cancel=self._on_selection_cancelled
        )
    
    def _on_region_selected(self, rect: Tuple[int, int, int, int]):
        """Handle region selection"""
        self.selection_overlay = None
        
        if self.current_mode == "screenshot":
            self.on_screenshot(rect)
            self._close()
        else:
            self.on_record(rect)
            self._close()
    
    def _on_selection_cancelled(self):
        """Handle selection cancelled"""
        self.selection_overlay = None
        self.deiconify()  # Show toolbar again
    
    def _close(self):
        """Close overlay"""
        if self.selection_overlay:
            try:
                self.selection_overlay.destroy()
            except:
                pass
        
        if self.on_close:
            self.on_close()
        
        self.destroy()
    
    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y
    
    def _do_drag(self, event):
        x = self.winfo_x() + (event.x - self._drag_x)
        y = self.winfo_y() + (event.y - self._drag_y)
        self.geometry(f"+{x}+{y}")


class SelectionOverlay(tk.Toplevel):
    """
    Fullscreen overlay for region selection.
    Lightweight Tk (not CTk) for performance.
    """
    
    def __init__(
        self, 
        on_select: Callable[[Tuple[int, int, int, int]], None],
        on_cancel: Callable
    ):
        super().__init__()
        
        self.on_select = on_select
        self.on_cancel = on_cancel
        
        # Fullscreen transparent overlay
        self.attributes("-fullscreen", True)
        self.attributes("-alpha", 0.3)
        self.attributes("-topmost", True)
        self.configure(bg="black", cursor="cross")
        
        # Canvas for drawing
        self.canvas = tk.Canvas(
            self, 
            bg="black", 
            highlightthickness=0,
            cursor="cross"
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Selection state
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.dim_label = None
        
        # Bindings
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Escape>", lambda e: self._cancel())
        
        # Instructions
        self.instructions = tk.Label(
            self.canvas,
            text="Выделите область. ESC для отмены.",
            font=("Segoe UI", 14),
            fg="white",
            bg="black",
            padx=15,
            pady=8
        )
        self.instructions.place(relx=0.5, rely=0.1, anchor="center")
        
        self.focus_force()
    
    def _on_press(self, event):
        self.start_x = self.winfo_pointerx()
        self.start_y = self.winfo_pointery()
        self.instructions.place_forget()
        
        # Create rectangle
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y,
            self.start_x, self.start_y,
            outline="#00F2FF",
            width=2
        )
        
        # Dimension label
        self.dim_label = tk.Label(
            self.canvas,
            text="0 x 0",
            font=("Consolas", 11),
            fg="#00F2FF",
            bg="black"
        )
    
    def _on_drag(self, event):
        if self.start_x is None:
            return
        
        cur_x = self.winfo_pointerx()
        cur_y = self.winfo_pointery()
        
        # Update rectangle
        self.canvas.coords(
            self.rect_id,
            self.start_x, self.start_y,
            cur_x, cur_y
        )
        
        # Update dimensions
        w = abs(cur_x - self.start_x)
        h = abs(cur_y - self.start_y)
        self.dim_label.configure(text=f"{w} × {h}")
        self.dim_label.place(x=cur_x + 10, y=cur_y + 10)
    
    def _on_release(self, event):
        if self.start_x is None:
            self._cancel()
            return
        
        end_x = self.winfo_pointerx()
        end_y = self.winfo_pointery()
        
        # Normalize
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        # Minimum size check
        if (x2 - x1) > 10 and (y2 - y1) > 10:
            self.destroy()
            self.on_select((x1, y1, x2, y2))
        else:
            self._cancel()
    
    def _cancel(self):
        self.destroy()
        self.on_cancel()
