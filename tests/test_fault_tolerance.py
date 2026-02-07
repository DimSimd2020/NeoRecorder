
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ffmpeg_handler import FFmpegHandler

class TestFaultTolerance(unittest.TestCase):
    def setUp(self):
        self.handler = FFmpegHandler()
        self.warning_called = False
        self.warning_msg = ""

        def on_warning(msg):
            self.warning_called = True
            self.warning_msg = msg

        self.handler.set_callbacks(on_warning=on_warning)

    @patch('subprocess.Popen')
    @patch('utils.ffmpeg_handler.FFmpegHandler._get_gdigrab_resolution')
    @patch('tempfile.mkdtemp')
    def test_retry_mechanism(self, mock_mkdtemp, mock_resolution, mock_popen):
        # Setup mocks
        mock_mkdtemp.return_value = "/tmp/neorecorder_test"
        mock_resolution.return_value = (1920, 1080)

        # Scenario:
        # First Popen call returns a process that has already exited (poll() returns a code)
        # Second Popen call returns a running process (poll() returns None)

        # Mock for failed process
        failed_process = MagicMock()
        failed_process.poll.return_value = 1  # Exited with error
        failed_process.returncode = 1
        failed_process.stderr.read.return_value = b"Error: Access Violation"

        # Mock for successful process
        success_process = MagicMock()
        success_process.poll.return_value = None  # Running
        success_process.returncode = None
        # Provide some initial output so monitor thread doesn't block or loop infinitely without data
        success_process.stderr.readline.side_effect = [
            b"frame=1 fps=30 size=100kB time=00:00:01.00 bitrate=1000kbits/s speed=1x",
            b""
        ]

        # Configure side_effect for Popen
        mock_popen.side_effect = [failed_process, success_process]

        # Initial encoder check mock - force it to think we have hardware
        with patch.object(self.handler, 'get_best_encoder', return_value='h264_qsv'):
            # Start recording
            result = self.handler.start_recording("output.mp4", framerate=60)

            # Assertions
            self.assertTrue(result, "Recording should succeed eventually")
            self.assertTrue(self.warning_called, "Warning callback should be triggered")
            self.assertIn("Safe Mode", self.warning_msg)

            # Verify Popen was called twice
            self.assertEqual(mock_popen.call_count, 2)

            # First call arguments (should try h264_qsv)
            args1, _ = mock_popen.call_args_list[0]
            cmd1 = args1[0]
            self.assertIn("h264_qsv", cmd1)

            # Second call arguments (should use libx264 due to fallback)
            args2, _ = mock_popen.call_args_list[1]
            cmd2 = args2[0]
            self.assertIn("libx264", cmd2)
            self.assertIn("ultrafast", cmd2)  # Should use ultrafast preset in safe mode

    @patch('subprocess.Popen')
    @patch('utils.ffmpeg_handler.FFmpegHandler._get_gdigrab_resolution')
    @patch('tempfile.mkdtemp')
    def test_immediate_crash_handling(self, mock_mkdtemp, mock_resolution, mock_popen):
        mock_mkdtemp.return_value = "/tmp/test"
        mock_resolution.return_value = (1920, 1080)

        # Mock immediate crash on both attempts
        process = MagicMock()
        process.poll.return_value = 1
        process.returncode = 1
        process.stderr.read.return_value = b"Fatal Error"

        mock_popen.return_value = process

        # Patch get_best_encoder to avoid extra Popen calls during encoder detection
        with patch.object(self.handler, 'get_best_encoder', return_value='h264_qsv'):
            # Start recording
            result = self.handler.start_recording("output.mp4")

            self.assertFalse(result, "Should return False if both attempts fail")
            self.assertTrue(self.warning_called) # Warning is called before second attempt
            self.assertEqual(mock_popen.call_count, 2)

if __name__ == '__main__':
    unittest.main()
