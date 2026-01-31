"""
Logger module for NeoRecorder.
Provides centralized logging with file and console output.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

# Global logger instance
_logger: Optional[logging.Logger] = None


def get_logger(name: str = "NeoRecorder") -> logging.Logger:
    """Get or create the application logger"""
    global _logger
    
    if _logger is not None:
        return _logger
    
    _logger = logging.getLogger(name)
    _logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate handlers
    if _logger.handlers:
        return _logger
    
    # Create logs directory
    log_dir = os.path.join(
        os.path.expanduser("~"), 
        "Videos", 
        "NeoRecorder", 
        "logs"
    )
    os.makedirs(log_dir, exist_ok=True)
    
    # Log filename with date
    log_filename = f"neorecorder_{datetime.now().strftime('%Y-%m-%d')}.log"
    log_path = os.path.join(log_dir, log_filename)
    
    # File handler (DEBUG level)
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    _logger.addHandler(file_handler)
    
    # Console handler (INFO level, only in dev mode)
    if not getattr(sys, 'frozen', False):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_format)
        _logger.addHandler(console_handler)
    
    _logger.info(f"Logger initialized. Log file: {log_path}")
    
    return _logger


def log_recording_start(output_path: str, fps: int, quality: str, encoder: str):
    """Log recording start event"""
    logger = get_logger()
    logger.info(f"Recording started: {output_path}")
    logger.info(f"  FPS: {fps}, Quality: {quality}, Encoder: {encoder}")


def log_recording_stop(output_path: str, duration: float, segments: int = 1):
    """Log recording stop event"""
    logger = get_logger()
    minutes, seconds = divmod(int(duration), 60)
    logger.info(f"Recording stopped: {output_path}")
    logger.info(f"  Duration: {minutes}m {seconds}s, Segments: {segments}")


def log_error(context: str, error: Exception):
    """Log an error with context"""
    logger = get_logger()
    logger.error(f"{context}: {type(error).__name__}: {error}")


def log_warning(message: str):
    """Log a warning"""
    logger = get_logger()
    logger.warning(message)


def log_debug(message: str):
    """Log debug information"""
    logger = get_logger()
    logger.debug(message)


def log_ffmpeg_output(line: str):
    """Log FFmpeg output line"""
    logger = get_logger()
    # Only log important FFmpeg messages
    if any(kw in line.lower() for kw in ['error', 'warning', 'failed', 'drop']):
        logger.warning(f"FFmpeg: {line}")
    else:
        logger.debug(f"FFmpeg: {line}")
