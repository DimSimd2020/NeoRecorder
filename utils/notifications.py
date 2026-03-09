"""Formatted toast notifications for NeoRecorder."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from utils.display_manager import DisplayBounds, get_display_manager


class NotificationKind(str, Enum):
    """Supported toast styles."""

    INFO = "info"
    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True)
class ToastStyle:
    """Visual style for a toast."""

    icon: str
    accent: str
    title_color: str
    body_color: str
    footer_color: str
    duration: float


@dataclass(frozen=True)
class ToastPayload:
    """Renderable toast data."""

    title: str
    message: str
    footer: str
    icon: str
    accent: str
    title_color: str
    body_color: str
    footer_color: str
    duration: float


TOAST_STYLES = {
    NotificationKind.INFO: ToastStyle("REC", "#27C1F4", "#F4FBFF", "#B5C9D8", "#86A2B6", 4.0),
    NotificationKind.SUCCESS: ToastStyle("OK", "#1FA971", "#F4FBFF", "#D7F8E8", "#8AD7B2", 5.0),
    NotificationKind.ERROR: ToastStyle("ERR", "#F26D3D", "#FFF6F3", "#FFD8CC", "#F2B39C", 5.0),
}


def build_toast_payload(
    title: str,
    message: str,
    kind: NotificationKind = NotificationKind.INFO,
    footer: str = "Click to dismiss",
    duration: Optional[float] = None,
) -> ToastPayload:
    """Build a formatted toast payload."""
    style = TOAST_STYLES[kind]
    return ToastPayload(
        title=_normalize_line(title, fallback="NeoRecorder"),
        message=_normalize_block(message, fallback=""),
        footer=_normalize_line(footer, fallback=""),
        icon=style.icon,
        accent=style.accent,
        title_color=style.title_color,
        body_color=style.body_color,
        footer_color=style.footer_color,
        duration=duration or style.duration,
    )


def compute_toast_geometry(bounds: DisplayBounds, scale: float, line_count: int) -> tuple[int, int, int, int]:
    """Return bottom-right geometry for a toast."""
    width = int(380 * scale)
    height = int((110 + max(0, line_count - 2) * 22) * scale)
    pad_x = int(26 * scale)
    pad_y = int(74 * scale)
    x = bounds.left + bounds.width - width - pad_x
    y = bounds.top + bounds.height - height - pad_y
    return width, height, x, y


def toast_line_count(payload: ToastPayload) -> int:
    """Count visible text lines for layout."""
    message_lines = max(1, len([line for line in payload.message.splitlines() if line.strip()]))
    footer_lines = 1 if payload.footer else 0
    return 1 + message_lines + footer_lines


def show_notification(
    title: str,
    message: str,
    kind: NotificationKind = NotificationKind.INFO,
    footer: str = "Click to dismiss",
    duration: Optional[float] = None,
):
    """Convenience function for toasts."""
    NeoToast.show(build_toast_payload(title, message, kind, footer, duration))


class NeoToast:
    """Single-instance toast renderer."""

    _active_toast = None

    @classmethod
    def show(cls, payload: ToastPayload):
        """Render a toast from a payload."""
        cls._close_active()
        root = cls._get_root()
        toast = cls._create_window(root)
        cls._active_toast = toast
        cls._layout_toast(toast, payload)
        cls._bind_close(toast)
        cls._fade_in(toast)
        toast.after(int(payload.duration * 1000), lambda: cls._fade_out(toast))

    @classmethod
    def _close_active(cls):
        if cls._active_toast is None:
            return
        try:
            cls._active_toast.destroy()
        except Exception:
            pass
        cls._active_toast = None

    @staticmethod
    def _get_root():
        root = tk._default_root
        if root is not None:
            return root
        root = tk.Tk()
        root.withdraw()
        return root

    @staticmethod
    def _create_window(root):
        toast = tk.Toplevel(root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.attributes("-alpha", 0.0)
        toast.configure(bg="#09131B")
        return toast

    @classmethod
    def _layout_toast(cls, toast, payload: ToastPayload):
        scale = cls._dpi_scale(toast)
        cls._position_toast(toast, payload, scale)
        frame = tk.Frame(toast, bg="#101B27", highlightbackground="#274459", highlightthickness=1)
        frame.pack(fill="both", expand=True)
        accent = tk.Frame(frame, bg=payload.accent, width=max(6, int(6 * scale)))
        accent.pack(side="left", fill="y")
        content = tk.Frame(frame, bg="#101B27")
        content.pack(fill="both", expand=True, padx=int(16 * scale), pady=int(14 * scale))
        cls._render_header(content, payload, scale)
        cls._render_message(content, payload, scale)
        cls._render_footer(content, payload, scale)

    @staticmethod
    def _dpi_scale(toast) -> float:
        try:
            scale = toast.winfo_fpixels("1i") / 96.0
        except Exception:
            scale = 1.0
        return max(1.0, min(scale, 2.25))

    @staticmethod
    def _position_toast(toast, payload: ToastPayload, scale: float):
        bounds = get_display_manager().get_primary_monitor().bounds
        width, height, x, y = compute_toast_geometry(bounds, scale, toast_line_count(payload))
        toast.geometry(f"{width}x{height}{_axis(x)}{_axis(y)}")

    @staticmethod
    def _render_header(content, payload: ToastPayload, scale: float):
        row = tk.Frame(content, bg="#101B27")
        row.pack(fill="x")
        icon = tk.Label(
            row,
            text=payload.icon,
            font=("Bahnschrift SemiBold", max(11, int(11 * scale)), "bold"),
            bg="#1B2D3F",
            fg=payload.accent,
            padx=int(10 * scale),
            pady=int(5 * scale),
        )
        icon.pack(side="left", padx=(0, int(12 * scale)))
        title = tk.Label(
            row,
            text=payload.title,
            font=("Bahnschrift SemiCondensed", max(15, int(15 * scale)), "bold"),
            bg="#101B27",
            fg=payload.title_color,
            anchor="w",
        )
        title.pack(fill="x")

    @staticmethod
    def _render_message(content, payload: ToastPayload, scale: float):
        message = tk.Label(
            content,
            text=payload.message,
            font=("Segoe UI", max(10, int(10 * scale))),
            bg="#101B27",
            fg=payload.body_color,
            justify="left",
            anchor="w",
            wraplength=int(280 * scale),
        )
        message.pack(fill="x", pady=(int(10 * scale), 0))

    @staticmethod
    def _render_footer(content, payload: ToastPayload, scale: float):
        if not payload.footer:
            return
        footer = tk.Label(
            content,
            text=payload.footer.upper(),
            font=("Consolas", max(9, int(9 * scale))),
            bg="#101B27",
            fg=payload.footer_color,
            anchor="w",
        )
        footer.pack(fill="x", pady=(int(10 * scale), 0))

    @classmethod
    def _bind_close(cls, toast):
        def close(_event=None):
            cls._fade_out(toast, start=0.95)

        cls._bind_tree(toast, close)

    @classmethod
    def _bind_tree(cls, widget, handler):
        widget.bind("<Button-1>", handler)
        for child in widget.winfo_children():
            cls._bind_tree(child, handler)

    @classmethod
    def _fade_in(cls, toast, alpha: float = 0.0):
        try:
            if not toast.winfo_exists():
                return
            if alpha >= 0.95:
                toast.attributes("-alpha", 0.95)
                return
            toast.attributes("-alpha", alpha)
            toast.after(18, lambda: cls._fade_in(toast, alpha + 0.12))
        except Exception:
            pass

    @classmethod
    def _fade_out(cls, toast, start: float = 0.95):
        try:
            if not toast.winfo_exists():
                return
            if start <= 0.0:
                toast.destroy()
                if cls._active_toast is toast:
                    cls._active_toast = None
                return
            toast.attributes("-alpha", start)
            toast.after(22, lambda: cls._fade_out(toast, start - 0.12))
        except Exception:
            pass


def show_recording_complete(title: str, message: str):
    """Show recording complete notification."""
    show_notification(title, message, NotificationKind.SUCCESS, footer="Saved to output folder")


def show_simple_notification(title: str, message: str):
    """Show generic notification."""
    show_notification(title, message, NotificationKind.INFO)


def show_error_notification(title: str, message: str):
    """Show error notification."""
    show_notification(title, message, NotificationKind.ERROR, footer="Open the app for details")


def _normalize_line(value: str, fallback: str) -> str:
    compact = " ".join(str(value or "").split())
    return compact or fallback


def _normalize_block(value: str, fallback: str) -> str:
    lines = [line.strip() for line in str(value or "").splitlines()]
    compact = "\n".join(line for line in lines if line)
    return compact or fallback


def _axis(value: int) -> str:
    return f"+{value}" if value >= 0 else str(value)
