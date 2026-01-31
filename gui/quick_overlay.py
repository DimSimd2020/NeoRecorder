"""
Quick Capture Overlay for NeoRecorder.
Toolbar + dimmed screen + region selection.
"""

import customtkinter as ctk
import tkinter as tk
from typing import Callable, Optional, Tuple
import ctypes
from PIL import ImageGrab, ImageTk, ImageEnhance
from config import NEON_BLUE, settings

# Windows constants
WDA_EXCLUDEFROMCAPTURE = 0x00000011


class QuickOverlay:
    """Quick capture: toolbar + dimmed screen + selection"""
    
    def __init__(
        self, 
        master,
        on_screenshot: Callable[[Tuple[int, int, int, int]], None],
        on_record: Callable[[Tuple[int, int, int, int]], None],
        on_close: Optional[Callable] = None
    ):
        self.master = master
        self.on_screenshot = on_screenshot
        self.on_record = on_record
        self.on_close = on_close
        
        self.current_mode = "screenshot"
        self._closed = False
        self._selecting = False
        
        # Screen info
        self.screen_width = master.winfo_screenwidth()
        self.screen_height = master.winfo_screenheight()
        
        # Settings
        self.dim_screen = settings.get("overlay_dim_screen", True)
        
        # Take screenshot
        self.screenshot = None
        self.bg_image = None
        try:
            self.screenshot = ImageGrab.grab()
            if self.dim_screen:
                enhancer = ImageEnhance.Brightness(self.screenshot)
                self.screenshot = enhancer.enhance(0.4)
        except:
            pass
        
        # Selection state
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.size_label_id = None
        
        # Create windows
        self._create_selection_window()
        self._create_toolbar()
    
    def _create_selection_window(self):
        """Create fullscreen selection overlay"""
        self.selection_win = tk.Toplevel(self.master)
        self.selection_win.overrideredirect(True)
        self.selection_win.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
        self.selection_win.attributes("-topmost", True)
        self.selection_win.configure(bg="black", cursor="cross")
        
        # Canvas
        self.canvas = tk.Canvas(
            self.selection_win,
            width=self.screen_width,
            height=self.screen_height,
            bg="black",
            highlightthickness=0,
            cursor="cross"
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Background
        if self.screenshot:
            self.bg_image = ImageTk.PhotoImage(self.screenshot)
            self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image, tags="bg")
        
        # Bindings
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.selection_win.bind("<Escape>", lambda e: self._close())
        
        self.selection_win.focus_force()
    
    def _create_toolbar(self):
        """Create floating toolbar using CTk for better appearance"""
        self.toolbar = ctk.CTkToplevel(self.master)
        self.toolbar.overrideredirect(True)
        self.toolbar.attributes("-topmost", True)
        self.toolbar.configure(fg_color="#1A1A1A")
        
        # Position
        toolbar_width = 180
        toolbar_height = 50
        x = (self.screen_width - toolbar_width) // 2
        y = 30
        self.toolbar.geometry(f"{toolbar_width}x{toolbar_height}+{x}+{y}")
        
        # Store position for hit testing
        self.toolbar_rect = (x, y, x + toolbar_width, y + toolbar_height)
        
        # Exclude from capture
        self.toolbar.after(10, self._set_exclusion)
        
        # Frame
        self.frame = ctk.CTkFrame(
            self.toolbar,
            fg_color="#2D2D2D",
            corner_radius=12,
            border_width=1,
            border_color="#444444"
        )
        self.frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Buttons container
        self.btn_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.btn_frame.pack(side="left", padx=10, pady=5)
        
        # Screenshot button
        self.screenshot_btn = ctk.CTkButton(
            self.btn_frame,
            text="📷",
            width=40,
            height=36,
            font=("Segoe UI Emoji", 18),
            fg_color=NEON_BLUE,
            hover_color="#00C8D4",
            corner_radius=8,
            command=self._mode_screenshot
        )
        self.screenshot_btn.pack(side="left", padx=2)
        
        # Record button
        self.record_btn = ctk.CTkButton(
            self.btn_frame,
            text="🎬",
            width=40,
            height=36,
            font=("Segoe UI Emoji", 18),
            fg_color="transparent",
            hover_color="#444444",
            corner_radius=8,
            command=self._mode_record
        )
        self.record_btn.pack(side="left", padx=2)
        
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
        
        # Drag binding
        self.frame.bind("<ButtonPress-1>", self._start_drag)
        self.frame.bind("<B1-Motion>", self._do_drag)
        self.toolbar.bind("<Escape>", lambda e: self._close())
        
        # Keep toolbar lifted
        self.toolbar.lift()
        self.toolbar.after(100, self._keep_lifted)
    
    def _set_exclusion(self):
        """Exclude toolbar from capture"""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.toolbar.winfo_id())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except:
            pass
    
    def _keep_lifted(self):
        """Keep toolbar on top"""
        if not self._closed:
            try:
                self.toolbar.lift()
                self.toolbar.after(100, self._keep_lifted)
            except:
                pass
    
    def _mode_screenshot(self):
        """Set screenshot mode"""
        self.current_mode = "screenshot"
        self.screenshot_btn.configure(fg_color=NEON_BLUE)
        self.record_btn.configure(fg_color="transparent")
    
    def _mode_record(self):
        """Set record mode"""
        self.current_mode = "record"
        self.screenshot_btn.configure(fg_color="transparent")
        self.record_btn.configure(fg_color="#FF4444")
    
    def _is_on_toolbar(self, x, y):
        """Check if click is on toolbar"""
        tx1, ty1, tx2, ty2 = self.toolbar_rect
        return tx1 <= x <= tx2 and ty1 <= y <= ty2
    
    def _on_press(self, event):
        """Mouse pressed"""
        # Check if on toolbar area
        if self._is_on_toolbar(event.x, event.y):
            return
        
        self._selecting = True
        self.start_x = event.x
        self.start_y = event.y
        
        # Create rectangle
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y,
            self.start_x, self.start_y,
            outline="#00F2FF",
            width=2,
            tags="selection"
        )
        
        # Size label
        self.size_label_id = self.canvas.create_text(
            self.start_x + 10, self.start_y - 20,
            text="0 × 0",
            fill="#00F2FF",
            font=("Consolas", 12),
            anchor="nw",
            tags="selection"
        )
    
    def _on_drag(self, event):
        """Mouse drag"""
        if not self._selecting or self.rect_id is None:
            return
        
        cur_x = event.x
        cur_y = event.y
        
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)
        
        w = abs(cur_x - self.start_x)
        h = abs(cur_y - self.start_y)
        
        label_x = max(cur_x, self.start_x) + 10
        label_y = min(cur_y, self.start_y) - 25
        if label_y < 10:
            label_y = max(cur_y, self.start_y) + 10
        
        self.canvas.coords(self.size_label_id, label_x, label_y)
        self.canvas.itemconfig(self.size_label_id, text=f"{w} × {h}")
    
    def _on_release(self, event):
        """Mouse released"""
        if not self._selecting or self._closed:
            return
        
        self._selecting = False
        
        if self.start_x is None:
            return
        
        end_x = event.x
        end_y = event.y
        
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        if (x2 - x1) > 10 and (y2 - y1) > 10:
            self._closed = True
            rect = (x1, y1, x2, y2)
            self._cleanup()
            
            if self.current_mode == "screenshot":
                self.on_screenshot(rect)
            else:
                self.on_record(rect)
            
            if self.on_close:
                self.on_close()
        else:
            self.canvas.delete("selection")
            self.start_x = None
            self.start_y = None
            self.rect_id = None
            self.size_label_id = None
    
    def _close(self):
        """Close overlay"""
        if self._closed:
            return
        self._closed = True
        self._cleanup()
        if self.on_close:
            self.on_close()
    
    def _cleanup(self):
        """Destroy windows"""
        try:
            self.selection_win.destroy()
        except:
            pass
        try:
            self.toolbar.destroy()
        except:
            pass
    
    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y
    
    def _do_drag(self, event):
        x = self.toolbar.winfo_x() + (event.x - self._drag_x)
        y = self.toolbar.winfo_y() + (event.y - self._drag_y)
        self.toolbar.geometry(f"+{x}+{y}")
        # Update rect
        self.toolbar.update_idletasks()
        w = self.toolbar.winfo_width()
        h = self.toolbar.winfo_height()
        self.toolbar_rect = (x, y, x + w, y + h)
    
    def destroy(self):
        self._close()
