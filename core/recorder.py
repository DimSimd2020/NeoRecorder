
"""
Screen Recorder module for NeoRecorder.
Manages recording sessions with async support and pause functionality.
"""

import os
import datetime
import time
import threading
from typing import Optional, Dict, Callable
from utils.ffmpeg_handler import FFmpegHandler
from config import DEFAULT_FORMAT, DEFAULT_FPS, DEFAULT_QUALITY

class ScreenRecorder:
    def __init__(self):
        self.handler = FFmpegHandler()
        self.is_recording = False
        self.output_dir = os.path.join(os.path.expanduser("~"), "Videos", "NeoRecorder")
        self.current_output_path: Optional[str] = None
        self.start_time: Optional[float] = None
        self.fps = DEFAULT_FPS
        self.quality = DEFAULT_QUALITY
        
        # Callbacks
        self._on_recording_complete: Optional[Callable[[Dict], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        
        # Thread safety
        self._lock = threading.RLock()
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def set_callbacks(self, on_complete=None, on_error=None):
        """Set callbacks for async events"""
        self._on_recording_complete = on_complete
        self._on_error = on_error
        
        # Also set handler callbacks
        self.handler.set_callbacks(
            on_stopped=self._handle_recording_stopped,
            on_error=self._handle_error
        )
    
    def _handle_recording_stopped(self, result: Dict):
        """Internal handler for recording stopped"""
        if self._on_recording_complete:
            self._on_recording_complete(result)
    
    def _handle_error(self, error: str):
        """Internal handler for errors"""
        if self._on_error:
            self._on_error(error)
    
    def set_fps(self, fps: int):
        """Set recording FPS"""
        with self._lock:
            self.fps = fps
    
    def set_quality(self, quality_preset: str):
        """Set quality preset"""
        with self._lock:
            self.quality = quality_preset

    def start(self, mode="fullscreen", rect=None, mic=None, system=False) -> Optional[str]:
        """
        Start recording and return output path.
        Non-blocking - recording runs in background.
        """
        with self._lock:
            if self.is_recording:
                return None
                
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"Record_{timestamp}.{DEFAULT_FORMAT}"
            self.current_output_path = os.path.join(self.output_dir, filename)
            self.start_time = time.time()

            self.handler.start_recording(
                self.current_output_path, 
                rect=rect, 
                mic=mic, 
                system=system,
                framerate=self.fps,
                quality_preset=self.quality
            )
            self.is_recording = True
            return self.current_output_path

    def start_async(self, mode="fullscreen", rect=None, mic=None, system=False) -> Optional[str]:
        """
        Start recording asynchronously (fully non-blocking).
        """
        with self._lock:
            if self.is_recording:
                return None
                
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"Record_{timestamp}.{DEFAULT_FORMAT}"
            self.current_output_path = os.path.join(self.output_dir, filename)
            self.start_time = time.time()

            self.handler.start_recording_async(
                self.current_output_path, 
                rect=rect, 
                mic=mic, 
                system=system,
                framerate=self.fps,
                quality_preset=self.quality
            )
            self.is_recording = True
            return self.current_output_path

    def stop(self) -> Optional[Dict]:
        """Stop recording and return metadata dict"""
        with self._lock:
            if not self.is_recording:
                return None
                
            result = self.handler.stop_recording()
            self.is_recording = False
            
            # Enrich result with additional info
            if result:
                result["path"] = self.output_dir
                result["full_path"] = result.get("output_path")
                result["duration_formatted"] = self._format_duration(result.get("duration", 0))
            
            return result
    
    def pause(self) -> bool:
        """Pause recording"""
        with self._lock:
            if not self.is_recording:
                return False
            return self.handler.pause()
    
    def resume(self) -> bool:
        """Resume paused recording"""
        with self._lock:
            if not self.is_recording:
                return False
            return self.handler.resume()
    
    def toggle_pause(self) -> bool:
        """Toggle pause state, returns new pause state"""
        with self._lock:
            if not self.is_recording:
                return False
            self.handler.toggle_pause()
            return self.handler.is_paused()
    
    def is_paused(self) -> bool:
        """Check if recording is paused"""
        return self.handler.is_paused()
    
    def get_elapsed_time(self) -> float:
        """Get elapsed recording time (excluding pauses)"""
        if not self.is_recording:
            return 0
        return self.handler.get_elapsed_time()
    
    def get_elapsed_formatted(self) -> str:
        """Get elapsed time as formatted string"""
        return self._format_duration(self.get_elapsed_time())
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds to HH:MM:SS"""
        seconds = int(seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def get_output_dir(self) -> str:
        return self.output_dir

    def set_output_dir(self, new_dir: str):
        with self._lock:
            if os.path.exists(new_dir):
                self.output_dir = new_dir
            else:
                os.makedirs(new_dir, exist_ok=True)
                self.output_dir = new_dir
    
    def get_available_encoders(self) -> list:
        """Get list of available hardware encoders"""
        return self.handler.get_available_encoders()
    
    def get_best_encoder(self) -> str:
        """Get the best encoder that will be used"""
        return self.handler.get_best_encoder()
    
    def get_current_settings(self) -> Dict:
        """Get current recording settings"""
        return {
            "fps": self.fps,
            "quality": self.quality,
            "encoder": self.get_best_encoder(),
            "output_dir": self.output_dir
        }
