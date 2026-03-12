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
        fill = self._layer_fill(index, source)
        outline = "#F0C24D" if source.transform.locked else "#B9D7E5"
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2)
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
        meta_text = self._layer_meta_text(source)
        if meta_text:
            self.canvas.create_text(
                x1 + 14,
                y1 + 52,
                anchor="nw",
                text=meta_text,
                font=("Segoe UI", 9),
                fill="#E6F0F6",
            )
        if source.transform.rotation_deg:
            self.canvas.create_text(
                x2 - 12,
                y1 + 14,
                anchor="ne",
                text=f"{int(source.transform.rotation_deg)}°",
                font=("Segoe UI", 10, "bold"),
                fill="#F4D35E",
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

    def _layer_fill(self, index, source):
        if source.kind.value == "color_source":
            return source.metadata.get("color", self.LAYER_COLORS[index % len(self.LAYER_COLORS)])
        return self.LAYER_COLORS[index % len(self.LAYER_COLORS)]

    @staticmethod
    def _layer_meta_text(source):
        if source.kind.value == "browser_source":
            return source.metadata.get("url", "Browser placeholder")
        if source.kind.value == "text_source":
            return source.metadata.get("text", "")
        if source.kind.value == "image_source":
            return source.metadata.get("path", source.target or "Image placeholder")
        if source.kind.value == "media_source":
            return source.metadata.get("preview_mode", "Media placeholder")
        if source.kind.value == "color_source":
            return source.metadata.get("color", "")
        return ""

    @staticmethod
    def _source_rect(source, scene_bounds):
        if source.bounds is None:
            rect = scene_bounds
        else:
            rect = source.bounds.to_rect()
        x1, y1, x2, y2 = rect
        crop = source.transform.crop
        cropped_left = x1 + crop.left
        cropped_top = y1 + crop.top
        cropped_right = max(cropped_left + 1, x2 - crop.right)
        cropped_bottom = max(cropped_top + 1, y2 - crop.bottom)
        width = max(1, int((cropped_right - cropped_left) * source.transform.scale_x))
        height = max(1, int((cropped_bottom - cropped_top) * source.transform.scale_y))
        left = cropped_left + source.transform.position_x
        top = cropped_top + source.transform.position_y
        return (left, top, left + width, top + height)

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

    def __init__(self, master, source, on_volume, on_mute, on_solo=None, **kwargs):
        super().__init__(master, fg_color="#1A2230", corner_radius=14, **kwargs)
        self.source = source
        self.on_volume = on_volume
        self.on_mute = on_mute
        self.on_solo = on_solo
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
        if self.on_solo:
            ctk.CTkButton(
                header,
                text="SOLO",
                width=62,
                height=28,
                fg_color="#D28A31" if self.source.audio.solo else "#203247",
                hover_color="#E3A44A" if self.source.audio.solo else "#2A425A",
                command=lambda: self.on_solo(self.source.source_id, not self.source.audio.solo),
            ).pack(side="right", padx=(0, 8))

        slider_row = ctk.CTkFrame(self, fg_color="transparent")
        slider_row.pack(fill="x", padx=12, pady=(0, 12))

        slider_class = getattr(ctk, "CTkSlider", None)
        if slider_class is None:
            self.slider = ctk.CTkFrame(slider_row, fg_color="#203247", height=16)
            self.slider.set = lambda *_args, **_kwargs: None
        else:
            self.slider = slider_class(
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
        meter_row = ctk.CTkFrame(self, fg_color="transparent")
        meter_row.pack(fill="x", padx=12, pady=(0, 10))
        VUMeter(meter_row, width=160, height=8).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkLabel(
            meter_row,
            text=f"PK {int(self.source.audio.peak_level * 100)} • RMS {int(self.source.audio.rms_level * 100)}",
            text_color="#86A2B6",
            font=("Segoe UI", 10),
        ).pack(side="right")
        info = self._info_text()
        if info:
            ctk.CTkLabel(
                self,
                text=info,
                anchor="w",
                justify="left",
                text_color="#86A2B6",
                font=("Segoe UI", 10),
            ).pack(fill="x", padx=12, pady=(0, 10))

    def _on_volume_change(self, value):
        self.on_volume(self.source.source_id, float(value))

    def _info_text(self):
        parts = []
        if self.source.audio.gain_db:
            parts.append(f"Gain {self.source.audio.gain_db:+.1f}dB")
        if self.source.audio.sync_offset_ms:
            parts.append(f"Sync {self.source.audio.sync_offset_ms}ms")
        if self.source.audio.monitoring_mode.value != "off":
            parts.append(self.source.audio.monitoring_mode.value.replace("_", " ").title())
        return " • ".join(parts)
