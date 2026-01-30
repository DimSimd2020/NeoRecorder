
import customtkinter as ctk
import tkinter as tk

class RegionOverlay(ctk.CTkToplevel):
    def __init__(self, on_select):
        super().__init__()
        self.on_select = on_select
        self.attributes("-alpha", 0.3)
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.config(cursor="cross")
        
        self.canvas = tk.Canvas(self, cursor="cross", bg="grey", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.dim_label = tk.Label(self.canvas, text="", font=("Arial", 12), fg="cyan", bg="black")
        
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.bind("<Escape>", lambda e: self.destroy())

    def on_button_press(self, event):
        self.start_x = self.winfo_pointerx()
        self.start_y = self.winfo_pointery()
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="cyan", width=2)

    def on_move_press(self, event):
        cur_x = self.winfo_pointerx()
        cur_y = self.winfo_pointery()
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
        
        w = abs(cur_x - self.start_x)
        h = abs(cur_y - self.start_y)
        self.dim_label.config(text=f"{w} x {h}")
        self.dim_label.place(x=cur_x + 10, y=cur_y + 10)

    def on_button_release(self, event):
        end_x = self.winfo_pointerx()
        end_y = self.winfo_pointery()
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        if x2 - x1 > 10 and y2 - y1 > 10:
            self.on_select((x1, y1, x2, y2))
        self.destroy()
