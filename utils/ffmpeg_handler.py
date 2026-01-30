
import subprocess
import os
import signal
import datetime
import time
from config import FFMPEG_PATH, QUALITY_PRESETS, USE_HARDWARE_ENCODER

class FFmpegHandler:
    def __init__(self):
        self.process = None
        self.current_output = None
        self.start_timestamp = None
        self._available_encoders = None

    def get_available_encoders(self):
        """Detect available hardware encoders"""
        if self._available_encoders is not None:
            return self._available_encoders
        
        self._available_encoders = []
        try:
            result = subprocess.run(
                [FFMPEG_PATH, "-encoders", "-hide_banner"],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout
            
            # Check for hardware encoders
            if "h264_nvenc" in output:
                self._available_encoders.append("h264_nvenc")  # NVIDIA
            if "h264_qsv" in output:
                self._available_encoders.append("h264_qsv")    # Intel Quick Sync
            if "h264_amf" in output:
                self._available_encoders.append("h264_amf")    # AMD AMF
            if "hevc_nvenc" in output:
                self._available_encoders.append("hevc_nvenc")
                
        except Exception as e:
            print(f"Error detecting encoders: {e}")
        
        return self._available_encoders

    def get_best_encoder(self):
        """Get the best available encoder (prefer hardware)"""
        if not USE_HARDWARE_ENCODER:
            return "libx264"
        
        encoders = self.get_available_encoders()
        priority = ["h264_nvenc", "h264_qsv", "h264_amf"]
        
        for enc in priority:
            if enc in encoders:
                return enc
        
        return "libx264"  # Fallback to software

    def start_recording(self, output_path, rect=None, mic=None, system=False, 
                       framerate=60, quality_preset="balanced"):
        """
        Start recording with specified parameters.
        
        Args:
            output_path: Path to save the video
            rect: (x1, y1, x2, y2) for region capture
            mic: Microphone device name
            system: Whether to capture system audio
            framerate: Target FPS (30-240)
            quality_preset: Key from QUALITY_PRESETS
        """
        self.current_output = output_path
        self.start_timestamp = time.time()
        
        # Try ddagrab first (high performance, Windows 10 20H1+)
        success = self._try_ffmpeg(output_path, "ddagrab", rect, mic, system, 
                                   framerate, quality_preset)
        
        if not success:
            print("ddagrab failed or not supported, falling back to gdigrab...")
            # Fallback to gdigrab (slower but more compatible)
            fallback_fps = min(framerate, 60)  # gdigrab struggles above 60fps
            self._try_ffmpeg(output_path, "gdigrab", rect, mic, system, 
                           fallback_fps, quality_preset)

    def _try_ffmpeg(self, output_path, input_format, rect, mic, system, 
                   framerate, quality_preset):
        """Build and execute FFmpeg command"""
        
        quality = QUALITY_PRESETS.get(quality_preset, QUALITY_PRESETS["balanced"])
        encoder = self.get_best_encoder()
        
        cmd = [FFMPEG_PATH, "-y"]
        
        # Input options
        cmd.extend(["-f", input_format])
        cmd.extend(["-framerate", str(framerate)])
        
        # Region capture
        if rect:
            x, y, x2, y2 = rect
            w, h = x2 - x, y2 - y
            # Ensure dimensions are even (required for most codecs)
            w = w if w % 2 == 0 else w - 1
            h = h if h % 2 == 0 else h - 1
            cmd.extend([
                "-offset_x", str(x),
                "-offset_y", str(y),
                "-video_size", f"{w}x{h}"
            ])
            
        cmd.extend(["-i", "desktop"])

        # Microphone input
        if mic:
            cmd.extend(["-f", "dshow", "-i", f"audio={mic}"])

        # Video encoding options
        cmd.extend(["-c:v", encoder])
        
        if encoder == "libx264":
            cmd.extend([
                "-preset", quality["preset"],
                "-tune", "zerolatency",
                "-crf", str(quality["crf"]),
            ])
        elif encoder == "h264_nvenc":
            # NVIDIA NVENC optimized settings
            cmd.extend([
                "-preset", "p4",  # balanced preset for NVENC
                "-tune", "ll",   # low latency
                "-rc", "vbr",
                "-cq", str(quality["crf"] + 5),  # NVENC uses different scale
                "-b:v", "0",
            ])
        elif encoder == "h264_qsv":
            # Intel Quick Sync
            cmd.extend([
                "-preset", "faster",
                "-global_quality", str(quality["crf"] + 5),
            ])
        elif encoder == "h264_amf":
            # AMD AMF
            cmd.extend([
                "-quality", "speed",
                "-rc", "cqp",
                "-qp_i", str(quality["crf"]),
                "-qp_p", str(quality["crf"]),
            ])
        
        cmd.extend([
            "-pix_fmt", "yuv420p",
            "-vsync", "cfr",  # Constant frame rate for stability
        ])
        
        cmd.append(output_path)

        # Log command
        log_path = output_path + ".log"
        self.log_file = open(log_path, "w", encoding="utf-8")
        self.log_file.write(f"Encoder: {encoder}\n")
        self.log_file.write(f"FPS: {framerate}\n")
        self.log_file.write(f"Quality: {quality_preset}\n")
        self.log_file.write(f"Command: {' '.join(cmd)}\n")
        self.log_file.flush()
        
        self.process = subprocess.Popen(
            cmd, 
            stdin=subprocess.PIPE, 
            stdout=self.log_file, 
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        
        # Give it a moment to see if it crashes immediately
        time.sleep(1)
        if self.process.poll() is not None:
            # Command failed
            self.log_file.close()
            self.process = None
            return False
            
        return True

    def stop_recording(self):
        """Stop recording and return metadata"""
        duration = 0
        if self.start_timestamp:
            duration = time.time() - self.start_timestamp
            
        if self.process:
            try:
                self.process.stdin.write(b"q")
                self.process.stdin.flush()
                self.process.wait(timeout=10)
            except Exception:
                try:
                    self.process.terminate()
                except:
                    pass
            self.process = None
            if hasattr(self, 'log_file') and self.log_file is not None:
                self.log_file.close()
                self.log_file = None
        
        result = {
            "output_path": self.current_output,
            "duration": duration,
            "filename": os.path.basename(self.current_output) if self.current_output else None
        }
        
        self.current_output = None
        self.start_timestamp = None
        
        return result

    @staticmethod
    def get_audio_devices():
        """Get list of audio devices via FFmpeg dshow"""
        cmd = [FFMPEG_PATH, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
        result = subprocess.run(cmd, capture_output=True)
        
        # Try different encodings for Windows
        for enc in ['utf-8', 'cp1251', 'cp866']:
            try:
                return result.stderr.decode(enc)
            except UnicodeDecodeError:
                continue
        return result.stderr.decode('utf-8', errors='ignore')
