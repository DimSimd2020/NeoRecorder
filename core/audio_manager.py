
import pyaudio
import numpy as np
import threading

class AudioManager:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.current_stream = None
        self.is_monitoring = False
        self.vu_level = 0
        self._lock = threading.Lock()

    def get_input_devices(self):
        devices = []
        try:
            info = self.pa.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount')
            for i in range(0, num_devices):
                device_info = self.pa.get_device_info_by_host_api_device_index(0, i)
                if device_info.get('maxInputChannels') > 0:
                    name = device_info.get('name')
                    # Fix for Windows encoding issues in PyAudio
                    try:
                        # The string is often UTF-8 bytes mistakenly decoded as CP1251 (or CP1252)
                        # We encode back to the 'wrong' encoding and decode correctly as UTF-8
                        # Try CP1251 first as it's common for RU Windows
                        try:
                            name = name.encode('cp1251').decode('utf-8')
                        except Exception:
                            name = name.encode('cp1252').decode('utf-8')
                    except Exception:
                        pass
                    devices.append({
                        'index': i,
                        'name': name
                    })
        except Exception as e:
            print(f"Error getting audio devices: {e}")
        return devices

    def start_monitoring(self, device_index):
        if self.is_monitoring:
            self.stop_monitoring()
        
        self.is_monitoring = True
        threading.Thread(target=self._monitor_thread, args=(device_index,), daemon=True).start()

    def stop_monitoring(self):
        self.is_monitoring = False

    def _monitor_thread(self, device_index):
        chunk = 1024
        format = pyaudio.paInt16
        channels = 1
        rate = 44100
        
        try:
            stream = self.pa.open(format=format,
                                  channels=channels,
                                  rate=rate,
                                  input=True,
                                  input_device_index=device_index,
                                  frames_per_buffer=chunk)
            
            while self.is_monitoring:
                data = stream.read(chunk, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                if len(audio_data) > 0:
                    peak = np.abs(audio_data).max()
                    # Normalize to 0-1 range (approx)
                    with self._lock:
                        self.vu_level = min(1.0, peak / 32768.0)
                
            stream.stop_stream()
            stream.close()
        except Exception as e:
            print(f"Audio monitoring error: {e}")
            self.is_monitoring = False

    def get_vu_level(self):
        with self._lock:
            return self.vu_level

    def __del__(self):
        self.pa.terminate()
