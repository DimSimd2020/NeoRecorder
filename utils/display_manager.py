"""Monitor discovery and virtual desktop helpers."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Optional

import mss


@dataclass(frozen=True)
class DisplayBounds:
    """Virtual desktop bounds."""

    left: int
    top: int
    width: int
    height: int

    def to_rect(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.left + self.width, self.top + self.height)

    def to_mss_box(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }

    def to_geometry(self) -> str:
        return f"{self.width}x{self.height}{self._axis(self.left)}{self._axis(self.top)}"

    @staticmethod
    def _axis(value: int) -> str:
        return f"+{value}" if value >= 0 else str(value)


@dataclass(frozen=True)
class DisplayMonitor:
    """Single monitor description."""

    index: int
    name: str
    bounds: DisplayBounds
    is_primary: bool = False

    def to_label(self) -> str:
        bounds = self.bounds
        return f"{self.name} • {bounds.width}x{bounds.height} • {bounds.left},{bounds.top}"


class DisplayManager:
    """Load and resolve monitor metadata."""

    def __init__(self, mss_factory=None):
        self._mss_factory = mss_factory or mss.mss

    def list_monitors(self) -> tuple[DisplayMonitor, ...]:
        monitors = self._read_monitors()
        if monitors:
            return monitors
        return (self._fallback_monitor(),)

    def get_monitor(self, index: int) -> DisplayMonitor:
        for monitor in self.list_monitors():
            if monitor.index == index:
                return monitor
        return self.get_primary_monitor()

    def get_primary_monitor(self) -> DisplayMonitor:
        return next(
            (monitor for monitor in self.list_monitors() if monitor.is_primary),
            self.list_monitors()[0],
        )

    def get_virtual_bounds(self) -> DisplayBounds:
        raw = self._read_raw_monitors()
        if raw:
            root = raw[0]
            return self._bounds_from_raw(root)

        primary = self.get_primary_monitor()
        return primary.bounds

    def _read_monitors(self) -> tuple[DisplayMonitor, ...]:
        raw = self._read_raw_monitors()
        if len(raw) < 2:
            return ()
        return tuple(
            DisplayMonitor(
                index=index,
                name=f"Display {index}",
                bounds=self._bounds_from_raw(raw[index]),
                is_primary=index == 1,
            )
            for index in range(1, len(raw))
        )

    def _read_raw_monitors(self) -> list[dict]:
        sct = None
        try:
            sct = self._mss_factory()
            return list(getattr(sct, "monitors", []))
        except Exception:
            return []
        finally:
            if sct and hasattr(sct, "close"):
                try:
                    sct.close()
                except Exception:
                    pass

    @staticmethod
    def _bounds_from_raw(raw: dict) -> DisplayBounds:
        return DisplayBounds(
            left=raw["left"],
            top=raw["top"],
            width=raw["width"],
            height=raw["height"],
        )

    @staticmethod
    def _fallback_monitor() -> DisplayMonitor:
        width = 1920
        height = 1080
        try:
            width = ctypes.windll.user32.GetSystemMetrics(0)
            height = ctypes.windll.user32.GetSystemMetrics(1)
        except Exception:
            pass

        return DisplayMonitor(
            index=1,
            name="Display 1",
            bounds=DisplayBounds(left=0, top=0, width=width, height=height),
            is_primary=True,
        )


_display_manager: Optional[DisplayManager] = None


def get_display_manager() -> DisplayManager:
    """Return shared display manager."""
    global _display_manager
    if _display_manager is None:
        _display_manager = DisplayManager()
    return _display_manager
