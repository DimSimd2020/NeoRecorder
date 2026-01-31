"""
Global Hotkey Manager for NeoRecorder.
Uses keyboard library for system-wide hotkey detection.
"""

import threading
from typing import Callable, Dict, Optional
from utils.logger import get_logger, log_debug


class HotkeyManager:
    """
    Lightweight global hotkey manager.
    Thread-safe, with proper cleanup.
    """
    
    def __init__(self):
        self._hotkeys: Dict[str, int] = {}  # hotkey_string -> hook_id
        self._callbacks: Dict[str, Callable] = {}
        self._keyboard = None
        self._running = False
        self._lock = threading.Lock()
        self._logger = get_logger()
    
    def _ensure_keyboard(self):
        """Lazy load keyboard module"""
        if self._keyboard is None:
            try:
                import keyboard
                self._keyboard = keyboard
            except ImportError:
                self._logger.error("keyboard module not installed")
                return False
        return True
    
    def register(self, hotkey: str, callback: Callable, action_name: str = "") -> bool:
        """
        Register a global hotkey.
        
        Args:
            hotkey: Hotkey string like "ctrl+shift+s"
            callback: Function to call when hotkey is pressed
            action_name: Optional name for logging
        
        Returns:
            True if registered successfully
        """
        if not hotkey or not callback:
            return False
        
        if not self._ensure_keyboard():
            return False
        
        with self._lock:
            # Unregister existing hotkey for this action
            if action_name and action_name in self._callbacks:
                self.unregister(action_name)
            
            try:
                # Normalize hotkey format
                hotkey = hotkey.lower().replace(" ", "")
                
                hook_id = self._keyboard.add_hotkey(
                    hotkey, 
                    callback, 
                    suppress=False,
                    trigger_on_release=False
                )
                
                key = action_name or hotkey
                self._hotkeys[key] = hook_id
                self._callbacks[key] = callback
                self._running = True
                
                log_debug(f"Hotkey registered: {hotkey} -> {action_name or 'callback'}")
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to register hotkey {hotkey}: {e}")
                return False
    
    def unregister(self, action_or_hotkey: str) -> bool:
        """Unregister a hotkey by action name or hotkey string"""
        if not self._ensure_keyboard():
            return False
        
        with self._lock:
            if action_or_hotkey in self._hotkeys:
                try:
                    self._keyboard.remove_hotkey(self._hotkeys[action_or_hotkey])
                    del self._hotkeys[action_or_hotkey]
                    if action_or_hotkey in self._callbacks:
                        del self._callbacks[action_or_hotkey]
                    return True
                except Exception as e:
                    self._logger.error(f"Failed to unregister hotkey: {e}")
            return False
    
    def unregister_all(self):
        """Unregister all hotkeys"""
        if not self._ensure_keyboard():
            return
        
        with self._lock:
            for key in list(self._hotkeys.keys()):
                try:
                    self._keyboard.remove_hotkey(self._hotkeys[key])
                except:
                    pass
            self._hotkeys.clear()
            self._callbacks.clear()
            self._running = False
    
    def is_registered(self, action_name: str) -> bool:
        """Check if action has a registered hotkey"""
        return action_name in self._hotkeys
    
    def get_registered_hotkeys(self) -> Dict[str, str]:
        """Get dict of action_name -> hotkey_string"""
        return {k: str(v) for k, v in self._hotkeys.items()}
    
    def stop(self):
        """Stop all hotkey listening and cleanup"""
        self.unregister_all()
        if self._keyboard:
            try:
                self._keyboard.unhook_all()
            except:
                pass
    
    def __del__(self):
        self.stop()


# Global instance
_hotkey_manager: Optional[HotkeyManager] = None


def get_hotkey_manager() -> HotkeyManager:
    """Get global hotkey manager instance"""
    global _hotkey_manager
    if _hotkey_manager is None:
        _hotkey_manager = HotkeyManager()
    return _hotkey_manager
