import customtkinter as ctk
from config import NEON_BLUE, BG_COLOR
from gui.studio_presenter import format_source_caption

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


class ScenePreview(ctk.CTkFrame):
    """Stylized preview canvas for scene layers."""

    LAYER_COLORS = ["#125E7A", "#0C8C72", "#C4661F", "#8C3A5D", "#6B4CC2"]

    def __init__(self, master, width=620, height=360, **kwargs):
        super().__init__(master, fg_color="#111722", corner_radius=18, **kwargs)
        self.preview_width = width
        self.preview_height = height
        self.canvas = ctk.CTkCanvas(
            self,
            width=width,
            height=height,
            bg="#111722",
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True, padx=16, pady=16)

    def render(self, scene):
        self.canvas.delete("all")
        self._draw_background()
        if scene is None or not scene.video_sources():
            self._draw_empty_state()
            return

        scene_bounds = self._scene_bounds(scene)
        for index, source in enumerate(scene.video_sources()):
            self._draw_layer(index, source, scene_bounds)

    def _draw_background(self):
        width = self.preview_width
        height = self.preview_height
        self.canvas.create_rectangle(0, 0, width, height, fill="#0A0F17", outline="")
        self.canvas.create_rectangle(18, 18, width - 18, height - 18, outline="#233142", width=2)
        self.canvas.create_text(
            32,
            26,
            anchor="nw",
            text="STUDIO PREVIEW",
            font=("Segoe UI", 12, "bold"),
            fill="#7FBFDB",
        )

    def _draw_empty_state(self):
        self.canvas.create_text(
            self.preview_width / 2,
            self.preview_height / 2,
            text="No video source",
            font=("Segoe UI", 22, "bold"),
            fill="#6F7D8B",
        )

    def _draw_layer(self, index, source, scene_bounds):
        x1, y1, x2, y2 = self._resolve_rect(index, source, scene_bounds)
        fill = self.LAYER_COLORS[index % len(self.LAYER_COLORS)]
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="#B9D7E5", width=2)
        self.canvas.create_text(
            x1 + 14,
            y1 + 14,
            anchor="nw",
            text=source.name,
            font=("Segoe UI", 12, "bold"),
            fill="#EAF8FF",
        )
        self.canvas.create_text(
            x1 + 14,
            y1 + 34,
            anchor="nw",
            text=format_source_caption(source),
            font=("Segoe UI", 10),
            fill="#D2E6F2",
        )

    def _resolve_rect(self, index, source, scene_bounds):
        width = self.preview_width
        height = self.preview_height
        left, top, right, bottom = scene_bounds
        source_left, source_top, source_right, source_bottom = self._source_rect(source, scene_bounds)
        scene_width = max(1, right - left)
        scene_height = max(1, bottom - top)
        scale_x = (width - 88) / scene_width
        scale_y = (height - 100) / scene_height
        scale = min(scale_x, scale_y, 1.0)
        x1 = 44 + int((source_left - left) * scale)
        y1 = 58 + int((source_top - top) * scale)
        x2 = x1 + max(70, int((source_right - source_left) * scale))
        y2 = y1 + max(52, int((source_bottom - source_top) * scale))
        inset = min(index * 10, 32)
        return (x1 + inset, y1 + inset, min(x2 + inset, width - 30), min(y2 + inset, height - 30))

    @staticmethod
    def _source_rect(source, scene_bounds):
        if source.bounds is None:
            return scene_bounds
        return source.bounds.to_rect()

    @staticmethod
    def _scene_bounds(scene):
        rects = []
        for source in scene.video_sources():
            if source.bounds is None:
                rects.append((0, 0, 1920, 1080))
                continue
            rects.append(source.bounds.to_rect())

        left = min(rect[0] for rect in rects)
        top = min(rect[1] for rect in rects)
        right = max(rect[2] for rect in rects)
        bottom = max(rect[3] for rect in rects)
        return (left, top, right, bottom)


class MixerStrip(ctk.CTkFrame):
    """Simple mixer strip for audio source control."""

    def __init__(self, master, source, on_volume, on_mute, **kwargs):
        super().__init__(master, fg_color="#1A2230", corner_radius=14, **kwargs)
        self.source = source
        self.on_volume = on_volume
        self.on_mute = on_mute
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(
            header,
            text=self.source.name,
            font=("Segoe UI", 13, "bold"),
            text_color="#F2FBFF",
        ).pack(side="left")

        mute_text = "UNMUTE" if self.source.muted else "MUTE"
        ctk.CTkButton(
            header,
            text=mute_text,
            width=72,
            height=28,
            fg_color="#A33A4F" if self.source.muted else "#203247",
            hover_color="#D2536C" if self.source.muted else "#2A425A",
            command=lambda: self.on_mute(self.source.source_id, not self.source.muted),
        ).pack(side="right")

        slider_row = ctk.CTkFrame(self, fg_color="transparent")
        slider_row.pack(fill="x", padx=12, pady=(0, 12))

        self.slider = ctk.CTkSlider(
            slider_row,
            from_=0,
            to=1,
            number_of_steps=20,
            progress_color=NEON_BLUE,
            button_color="#F27F29",
            button_hover_color="#FF9F3E",
            command=self._on_volume_change,
        )
        self.slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.slider.set(self.source.volume)

        ctk.CTkLabel(
            slider_row,
            text=f"{int(self.source.volume * 100)}%",
            width=44,
            text_color="#C2D5E2",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="right")

    def _on_volume_change(self, value):
        self.on_volume(self.source.source_id, float(value))
