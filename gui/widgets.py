
import customtkinter as ctk
from config import NEON_BLUE, BG_COLOR

class VUMeter(ctk.CTkFrame):
    def __init__(self, master, width=200, height=10, **kwargs):
        super().__init__(master, width=width, height=height, fg_color=BG_COLOR, **kwargs)
        self.canvas = ctk.CTkCanvas(self, width=width, height=height, bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.level = 0
        self.width = width
        self.height = height
        self._draw_meter()

    def set_level(self, level):
        """level from 0 to 1"""
        self.level = level
        self._draw_meter()

    def _draw_meter(self, *args, **kwargs):
        self.canvas.delete("all")
        # Background bar
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill="#3D3D3D", outline="")
        # Level bar
        fill_width = self.level * self.width
        self.canvas.create_rectangle(0, 0, fill_width, self.height, fill=NEON_BLUE, outline="")
