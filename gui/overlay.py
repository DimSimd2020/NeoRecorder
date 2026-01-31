"""
Region Overlay for NeoRecorder.
Fullscreen overlay for selecting screen recording region.
"""

import customtkinter as ctk
import tkinter as tk
from typing import Callable, Tuple, Optional


class RegionOverlay(ctk.CTkToplevel):
    def __init__(self, on_select: Callable[[Tuple[int, int, int, int]], None]):
        super().__init__()
        self.on_select = on_select
        
        # Window setup
        self.attributes("-alpha", 0.3)
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.config(cursor="cross")
        
        # Canvas for drawing selection
        self.canvas = tk.Canvas(
            self, 
            cursor="cross", 
            bg="grey", 
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Selection state
        self.start_x: Optional[int] = None
        self.start_y: Optional[int] = None
        self.rect: Optional[int] = None
        
        # Dimension label
        self.dim_label = tk.Label(
            self.canvas, 
            text="", 
            font=("Arial", 12), 
            fg="cyan", 
            bg="black"
        )
        
        # Instructions label
        self.instructions = tk.Label(
            self.canvas,
            text="Drag to select region. Press Escape to cancel.",
            font=("Arial", 14),
            fg="white",
            bg="black",
            padx=10,
            pady=5
        )
        self.instructions.place(relx=0.5, rely=0.1, anchor="center")
        
        # Bindings
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.bind("<Escape>", self._on_cancel)
        
        # Focus to receive key events
        self.focus_force()

    def on_button_press(self, event):
        """Handle mouse button press - start selection"""
        self.start_x = self.winfo_pointerx()
        self.start_y = self.winfo_pointery()
        
        # Hide instructions
        self.instructions.place_forget()
        
        # Create rectangle
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, 
            self.start_x, self.start_y,
            outline="cyan", 
            width=2
        )

    def on_move_press(self, event):
        """Handle mouse drag - update selection"""
        if self.start_x is None or self.start_y is None:
            return
        
        cur_x = self.winfo_pointerx()
        cur_y = self.winfo_pointery()
        
        # Update rectangle
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
        
        # Update dimension label
        w = abs(cur_x - self.start_x)
        h = abs(cur_y - self.start_y)
        self.dim_label.config(text=f"{w} x {h}")
        self.dim_label.place(x=cur_x + 10, y=cur_y + 10)

    def on_button_release(self, event):
        """Handle mouse button release - finalize selection"""
        if self.start_x is None or self.start_y is None:
            self.destroy()
            return
        
        end_x = self.winfo_pointerx()
        end_y = self.winfo_pointery()
        
        # Normalize coordinates
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        # Minimum size check
        if x2 - x1 > 10 and y2 - y1 > 10:
            self.on_select((x1, y1, x2, y2))
        
        self.destroy()

    def _on_cancel(self, event=None):
        """Handle Escape key - cancel selection"""
        self.destroy()
