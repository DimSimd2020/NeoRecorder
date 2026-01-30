
"""
Audio Session Manager for per-application audio capture.
Uses pycaw to interface with Windows Audio Session API (WASAPI).
"""

import threading
from typing import List, Dict, Optional

class AudioSession:
    """Represents an audio session (application)"""
    def __init__(self, name: str, pid: int, volume: float, muted: bool, icon_path: Optional[str] = None):
        self.name = name
        self.pid = pid
        self.volume = volume
        self.muted = muted
        self.icon_path = icon_path

class AudioSessionManager:
    """Manages per-application audio sessions using WASAPI"""
    
    def __init__(self):
        self._sessions_cache: List[AudioSession] = []
        self._lock = threading.Lock()
        self._pycaw_available = self._check_pycaw()
    
    def _check_pycaw(self) -> bool:
        """Check if pycaw is available"""
        try:
            from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
            return True
        except ImportError:
            print("pycaw not installed. Per-app audio capture limited.")
            return False
    
    def get_active_audio_sessions(self) -> List[AudioSession]:
        """
        Get list of applications currently producing audio.
        
        Returns:
            List of AudioSession objects
        """
        if not self._pycaw_available:
            return []
        
        sessions = []
        try:
            from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
            from comtypes import CLSCTX_ALL
            
            audio_sessions = AudioUtilities.GetAllSessions()
            
            for session in audio_sessions:
                if session.Process:
                    try:
                        # Get volume interface
                        volume_interface = session._ctl.QueryInterface(ISimpleAudioVolume)
                        current_volume = volume_interface.GetMasterVolume()
                        is_muted = volume_interface.GetMute()
                        
                        audio_session = AudioSession(
                            name=session.Process.name(),
                            pid=session.Process.pid,
                            volume=current_volume,
                            muted=bool(is_muted)
                        )
                        sessions.append(audio_session)
                    except Exception as e:
                        # Some sessions may not have volume control
                        pass
        except Exception as e:
            print(f"Error getting audio sessions: {e}")
        
        with self._lock:
            self._sessions_cache = sessions
        
        return sessions
    
    def get_session_names(self) -> List[str]:
        """Get list of application names with active audio"""
        sessions = self.get_active_audio_sessions()
        return list(set([s.name for s in sessions]))
    
    def mute_session(self, process_name: str, mute: bool = True) -> bool:
        """
        Mute or unmute a specific application.
        
        Args:
            process_name: Name of the process
            mute: True to mute, False to unmute
            
        Returns:
            True if successful
        """
        if not self._pycaw_available:
            return False
        
        try:
            from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
            
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process and session.Process.name() == process_name:
                    volume_interface = session._ctl.QueryInterface(ISimpleAudioVolume)
                    volume_interface.SetMute(mute, None)
                    return True
        except Exception as e:
            print(f"Error muting session {process_name}: {e}")
        
        return False
    
    def set_session_volume(self, process_name: str, volume: float) -> bool:
        """
        Set volume for a specific application.
        
        Args:
            process_name: Name of the process
            volume: Volume level (0.0 to 1.0)
            
        Returns:
            True if successful
        """
        if not self._pycaw_available:
            return False
        
        try:
            from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
            
            volume = max(0.0, min(1.0, volume))  # Clamp to valid range
            
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process and session.Process.name() == process_name:
                    volume_interface = session._ctl.QueryInterface(ISimpleAudioVolume)
                    volume_interface.SetMasterVolume(volume, None)
                    return True
        except Exception as e:
            print(f"Error setting volume for {process_name}: {e}")
        
        return False
    
    def get_loopback_devices(self) -> List[Dict]:
        """
        Get list of audio loopback devices (for capturing system audio).
        
        Returns:
            List of device dictionaries with 'name' and 'id'
        """
        devices = []
        try:
            from pycaw.pycaw import AudioUtilities
            
            device = AudioUtilities.GetSpeakers()
            if device:
                devices.append({
                    'name': 'System Audio (Loopback)',
                    'id': 'loopback'
                })
        except Exception as e:
            print(f"Error getting loopback devices: {e}")
        
        return devices
    
    @staticmethod
    def install_dependencies():
        """Install pycaw if not present"""
        import subprocess
        import sys
        
        try:
            import pycaw
        except ImportError:
            print("Installing pycaw for per-app audio...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pycaw"])
