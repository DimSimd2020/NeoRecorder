"""
Audio Manager for NeoRecorder.
Handles audio input devices and VU meter monitoring.
"""

import pyaudio
import numpy as np
import threading
from typing import List, Dict, Optional


class AudioManager:
    def __init__(self):
        self.pa: Optional[pyaudio.PyAudio] = None
        self.current_stream = None
        self.is_monitoring = False
        self.vu_level = 0
        self._lock = threading.Lock()
        self._initialized = False
        self._init_pyaudio()
    
    def _init_pyaudio(self):
        """Initialize PyAudio with error handling"""
        try:
            self.pa = pyaudio.PyAudio()
            self._initialized = True
        except Exception as e:
            print(f"Failed to initialize PyAudio: {e}")
            self.pa = None
            self._initialized = False

    def get_input_devices(self) -> List[Dict]:
        """Get list of audio input devices"""
        if not self._initialized or not self.pa:
            return []
        
        devices = []
        try:
            info = self.pa.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount', 0)
            
            for i in range(num_devices):
                try:
                    device_info = self.pa.get_device_info_by_host_api_device_index(0, i)
                    if device_info.get('maxInputChannels', 0) > 0:
                        name = device_info.get('name', f'Device {i}')
                        # Fix for Windows encoding issues in PyAudio
                        name = self._fix_device_name_encoding(name)
                        devices.append({
                            'index': i,
                            'name': name
                        })
                except Exception as e:
                    print(f"Error getting device {i}: {e}")
                    
        except Exception as e:
            print(f"Error getting audio devices: {e}")
        
        return devices
    
    @staticmethod
    def _fix_device_name_encoding(name: str) -> str:
        """Fix common Windows encoding issues with device names"""
        if not name:
            return "Unknown Device"
        
        # Try to fix CP1251 -> UTF-8 encoding issues
        try:
            name = name.encode('cp1251').decode('utf-8')
        except Exception:
            try:
                name = name.encode('cp1252').decode('utf-8')
            except Exception:
                pass
        
        return name

    def start_monitoring(self, device_index: int):
        """Start VU meter monitoring for specified device"""
        if not self._initialized or not self.pa:
            print("PyAudio not initialized")
            return
        
        if self.is_monitoring:
            self.stop_monitoring()
        
        self.is_monitoring = True
        thread = threading.Thread(
            target=self._monitor_thread, 
            args=(device_index,), 
            daemon=True,
            name="AudioMonitor"
        )
        thread.start()

    def stop_monitoring(self):
        """Stop VU meter monitoring"""
        self.is_monitoring = False
        # Reset level
        with self._lock:
            self.vu_level = 0
            
        # Give a small time for thread to exit
        import time
        time.sleep(0.1)

    def _monitor_thread(self, device_index: int):
        """Thread function for audio level monitoring"""
        chunk = 1024
        audio_format = pyaudio.paInt16
        channels = 1
        rate = 44100
        
        stream = None
        try:
            stream = self.pa.open(
                format=audio_format,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=chunk
            )
            
            while self.is_monitoring:
                try:
                    data = stream.read(chunk, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    if len(audio_data) > 0:
                        peak = np.abs(audio_data).max()
                        # Normalize to 0-1 range
                        with self._lock:
                            self.vu_level = min(1.0, peak / 32768.0)
                except Exception as e:
                    print(f"Audio read error: {e}")
                    break
        except Exception as e:
            print(f"Audio monitoring error: {e}")
        finally:
            # Always cleanup stream
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            self.is_monitoring = False

    def get_vu_level(self) -> float:
        """Get current VU meter level (0.0 - 1.0)"""
        with self._lock:
            return self.vu_level

    def terminate(self):
        """Clean up resources"""
        self.stop_monitoring()
        
        if self.pa:
            try:
                self.pa.terminate()
            except Exception:
                pass
            self.pa = None
        
        self._initialized = False

    def __del__(self):
        """Destructor - clean up on garbage collection"""
        self.terminate()
