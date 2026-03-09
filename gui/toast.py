"""Compatibility wrapper for toast notifications."""

from __future__ import annotations

from utils.notifications import NotificationKind, show_notification


class ToastNotification:
    """Legacy adapter around the shared toast renderer."""

    @classmethod
    def show(cls, master, title: str, message: str, duration: int = 3000):
        """Show a toast via the shared notification renderer."""
        if master:
            master.after(
                0,
                lambda: show_notification(
                    title,
                    message,
                    kind=NotificationKind.INFO,
                    duration=max(duration, 500) / 1000,
                ),
            )


def show_toast(master, title: str, message: str, duration: int = 3000):
    """Convenience wrapper for legacy imports."""
    ToastNotification.show(master, title, message, duration)
