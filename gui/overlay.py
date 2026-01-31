"""
Region Overlay for NeoRecorder.
Wrapper around universal RegionSelector for backwards compatibility.
"""

from typing import Callable, Tuple
from utils.region_selector import RegionSelector
from config import settings


class RegionOverlay:
    """
    Region selection overlay for screen recording.
    Uses universal RegionSelector internally.
    """
    
    def __init__(self, master, on_select: Callable[[Tuple[int, int, int, int]], None]):
        """
        Initialize region overlay.
        
        Args:
            master: Parent Tk window
            on_select: Callback when region is selected, receives (x1, y1, x2, y2)
        """
        self.on_select = on_select
        
        # Get settings
        dim_screen = settings.get("overlay_dim_screen", True)
        lock_input = settings.get("overlay_lock_input", True)
        
        # Create region selector
        self._selector = RegionSelector(
            master=master,
            on_select=self._on_selected,
            on_cancel=self._on_cancelled,
            dim_screen=dim_screen,
            lock_input=lock_input,
            show_instructions=True
        )
    
    def _on_selected(self, rect: Tuple[int, int, int, int]):
        """Handle region selected"""
        self.on_select(rect)
    
    def _on_cancelled(self):
        """Handle selection cancelled"""
        pass  # Just close, no action needed
    
    def destroy(self):
        """Destroy overlay"""
        try:
            self._selector.destroy()
        except:
            pass
