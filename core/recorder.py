
import os
import datetime
import time
from utils.ffmpeg_handler import FFmpegHandler
from config import DEFAULT_FORMAT, DEFAULT_FPS, DEFAULT_QUALITY

class ScreenRecorder:
    def __init__(self):
        self.handler = FFmpegHandler()
        self.is_recording = False
        self.output_dir = os.path.join(os.path.expanduser("~"), "Videos", "NeoRecorder")
        self.current_output_path = None
        self.start_time = None
        self.fps = DEFAULT_FPS
        self.quality = DEFAULT_QUALITY
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def set_fps(self, fps):
        """Set recording FPS"""
        self.fps = fps
    
    def set_quality(self, quality_preset):
        """Set quality preset"""
        self.quality = quality_preset

    def start(self, mode="fullscreen", rect=None, mic=None, system=False):
        """Start recording and return output path"""
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

    def stop(self):
        """Stop recording and return metadata dict"""
        if self.is_recording:
            result = self.handler.stop_recording()
            self.is_recording = False
            
            # Calculate actual duration
            duration = time.time() - self.start_time if self.start_time else 0
            
            return {
                "filename": result.get("filename"),
                "path": self.output_dir,
                "full_path": result.get("output_path"),
                "duration": duration,
                "duration_formatted": self._format_duration(duration)
            }
        return None
    
    @staticmethod
    def _format_duration(seconds):
        """Format seconds to HH:MM:SS"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def get_output_dir(self):
        return self.output_dir

    def set_output_dir(self, new_dir):
        if os.path.exists(new_dir):
            self.output_dir = new_dir
        else:
            os.makedirs(new_dir, exist_ok=True)
            self.output_dir = new_dir
    
    def get_available_encoders(self):
        """Get list of available hardware encoders"""
        return self.handler.get_available_encoders()
    
    def get_best_encoder(self):
        """Get the best encoder that will be used"""
        return self.handler.get_best_encoder()
