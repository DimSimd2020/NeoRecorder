"""
Universal Region Selector for NeoRecorder.
Reusable component for selecting screen regions with dimming and visual feedback.
"""

import tkinter as tk
from typing import Callable, Optional, Tuple
from PIL import ImageGrab, ImageTk, ImageEnhance


class RegionSelector:
    """
    Fullscreen overlay for selecting a screen region.
    Shows dimmed screenshot background with visual feedback.
    
    Usage:
        def on_selected(rect):
            print(f"Selected: {rect}")
        
        selector = RegionSelector(
            master=root,
            on_select=on_selected,
            on_cancel=lambda: print("Cancelled"),
            dim_screen=True,
            lock_input=True
        )
    """
    
    def __init__(
        self,
        master,
        on_select: Callable[[Tuple[int, int, int, int]], None],
        on_cancel: Optional[Callable] = None,
        dim_screen: bool = True,
        lock_input: bool = True,
        show_instructions: bool = True
    ):
        """
        Initialize region selector.
        
        Args:
            master: Parent Tk window
            on_select: Callback when region selected, receives (x1, y1, x2, y2)
            on_cancel: Callback when cancelled (ESC or too small selection)
            dim_screen: Whether to dim the screen (default True)
            lock_input: Whether to block input to other windows (default True)
            show_instructions: Whether to show instruction text (default True)
        """
        self.master = master
        self.on_select = on_select
        self.on_cancel = on_cancel
        self._closed = False
        
        # Get screen dimensions
        self.screen_width = master.winfo_screenwidth()
        self.screen_height = master.winfo_screenheight()
        
        # Take screenshot for background
        self.screenshot = None
        self.bg_image = None
        try:
            self.screenshot = ImageGrab.grab()
            if dim_screen:
                enhancer = ImageEnhance.Brightness(self.screenshot)
                self.screenshot = enhancer.enhance(0.4)  # 40% brightness
        except Exception as e:
            print(f"Screenshot grab failed: {e}")
        
        # Create window
        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True)
        self.window.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
        self.window.attributes("-topmost", True)
        self.window.configure(bg="black", cursor="cross")
        
        # Canvas
        self.canvas = tk.Canvas(
            self.window,
            width=self.screen_width,
            height=self.screen_height,
            bg="black",
            highlightthickness=0,
            cursor="cross"
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Background image
        if self.screenshot:
            self.bg_image = ImageTk.PhotoImage(self.screenshot)
            self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image, tags="bg")
        
        # Instructions
        if show_instructions:
            self.instructions_id = self.canvas.create_text(
                self.screen_width // 2, 50,
                text="Выделите область мышью. ESC — отмена.",
                fill="white",
                font=("Segoe UI", 16),
                tags="ui"
            )
            # Background for instructions
            bbox = self.canvas.bbox(self.instructions_id)
            if bbox:
                self.canvas.create_rectangle(
                    bbox[0] - 15, bbox[1] - 8,
                    bbox[2] + 15, bbox[3] + 8,
                    fill="#1a1a1a",
                    outline="#444",
                    tags="ui"
                )
                self.canvas.tag_raise(self.instructions_id)
        
        # Selection state
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.size_label_id = None
        
        # Bindings
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.window.bind("<Escape>", lambda e: self._cancel())
        
        # Lock input
        if lock_input:
            self.window.grab_set()
        
        self.window.focus_force()
        self.window.lift()
    
    def _on_press(self, event):
        """Mouse pressed - start selection"""
        self.start_x = event.x
        self.start_y = event.y
        
        # Hide instructions
        self.canvas.delete("ui")
        
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
        """Mouse drag - update selection"""
        if self.start_x is None:
            return
        
        cur_x = event.x
        cur_y = event.y
        
        # Update rectangle
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)
        
        # Calculate size
        w = abs(cur_x - self.start_x)
        h = abs(cur_y - self.start_y)
        
        # Position label
        label_x = max(cur_x, self.start_x) + 10
        label_y = min(cur_y, self.start_y) - 25
        if label_y < 10:
            label_y = max(cur_y, self.start_y) + 10
        
        self.canvas.coords(self.size_label_id, label_x, label_y)
        self.canvas.itemconfig(self.size_label_id, text=f"{w} × {h}")
    
    def _on_release(self, event):
        """Mouse released - finish selection"""
        if self._closed or self.start_x is None:
            return
        
        end_x = event.x
        end_y = event.y
        
        # Normalize coordinates
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        # Minimum size check (10x10 pixels)
        if (x2 - x1) > 10 and (y2 - y1) > 10:
            self._closed = True
            rect = (x1, y1, x2, y2)
            self._cleanup()
            self.on_select(rect)
        else:
            # Too small - reset for new selection
            self.canvas.delete("selection")
            self.start_x = None
            self.start_y = None
    
    def _cancel(self):
        """Cancel selection"""
        if self._closed:
            return
        self._closed = True
        self._cleanup()
        if self.on_cancel:
            self.on_cancel()
    
    def _cleanup(self):
        """Clean up window"""
        try:
            self.window.grab_release()
        except:
            pass
        try:
            self.window.destroy()
        except:
            pass
    
    def destroy(self):
        """External destroy call"""
        self._cancel()
