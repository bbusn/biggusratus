import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from client.commands.webcam_stream import WebcamStreamCommand


class TestWebcamStreamCommand:
    def setup_method(self) -> None:
        WebcamStreamCommand._instance = None
        self.command = WebcamStreamCommand()

    def teardown_method(self) -> None:
        if self.command._running:
            self.command._stop()

    def test_name_property(self) -> None:
        assert self.command.name == "webcam_stream"

    def test_description_property(self) -> None:
        assert "stream" in self.command.description.lower()
        assert "webcam" in self.command.description.lower()

    def test_singleton_pattern(self) -> None:
        command2 = WebcamStreamCommand()
        assert command2 is self.command

    def test_execute_invalid_action(self) -> None:
        result = self.command.execute({"action": "invalid"})
        assert result["success"] is False
        assert "Invalid action" in result["error"]

    def test_execute_missing_action(self) -> None:
        result = self.command.execute({})
        assert result["success"] is False
        assert "Invalid action" in result["error"]

    def test_start_stream(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            result = self.command.execute({"action": "start"})

            assert result["success"] is True
            assert result["status"] == "started"
            assert "camera" in result
            assert "fps" in result

    def test_start_already_running(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            self.command.execute({"action": "start"})
            result = self.command.execute({"action": "start"})

            assert result["success"] is True
            assert result["status"] == "already_running"

    def test_stop_stream(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            self.command.execute({"action": "start"})
            result = self.command.execute({"action": "stop"})

            assert result["success"] is True
            assert result["status"] == "stopped"

    def test_stop_not_running(self) -> None:
        result = self.command.execute({"action": "stop"})
        assert result["success"] is True
        assert result["status"] == "not_running"

    def test_status_not_running(self) -> None:
        result = self.command.execute({"action": "status"})

        assert result["success"] is True
        assert result["status"] == "stopped"
        assert result["frame_count"] == 0

    def test_status_running(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            self.command.execute({"action": "start"})
            result = self.command.execute({"action": "status"})

            assert result["success"] is True
            assert result["status"] == "running"

    def test_get_frame_no_frames(self) -> None:
        result = self.command.execute({"action": "get_frame"})
        assert result["success"] is False
        assert "No frames available" in result["error"]

    def test_get_frames_empty(self) -> None:
        result = self.command.execute({"action": "get_frames"})
        assert result["success"] is True
        assert result["frames"] == []
        assert result["buffered_count"] == 0

    def test_start_with_custom_params(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            result = self.command.execute({
                "action": "start",
                "camera": 1,
                "fps": 30,
                "quality": 85,
            })

            assert result["success"] is True
            assert result["camera"] == 1
            assert result["fps"] == 30
            assert result["quality"] == 85

    def test_start_with_invalid_fps(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            result = self.command.execute({"action": "start", "fps": 100})
            assert result["fps"] == 15

            self.command._stop()

            result = self.command.execute({"action": "start", "fps": -1})
            assert result["fps"] == 15

    def test_start_with_invalid_quality(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            result = self.command.execute({"action": "start", "quality": 150})
            assert result["quality"] == 70

    def test_start_with_invalid_camera_type(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            result = self.command.execute({"action": "start", "camera": "invalid"})
            assert result["camera"] == 0

    def test_get_available_cameras(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_vc.return_value = mock_cap

            cameras = self.command.get_available_cameras()
            assert len(cameras) == 10

    def test_stream_worker_captures_frames(self) -> None:
        mock_frame = MagicMock()
        mock_frame.shape = (480, 640, 3)

        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc, \
             patch("client.commands.webcam_stream.cv2.imencode") as mock_encode:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (True, mock_frame)
            mock_vc.return_value = mock_cap

            mock_encode.return_value = (True, MagicMock(tobytes=MagicMock(return_value=b"encoded")))

            result = self.command.execute({"action": "start", "fps": 30})
            assert result["success"] is True

            time.sleep(0.2)

            self.command._stop()

            assert self.command._frame_count > 0

    def test_encode_frame(self) -> None:
        mock_frame = MagicMock()
        mock_frame.shape = (480, 640, 3)

        with patch("client.commands.webcam_stream.cv2.imencode") as mock_encode, \
             patch("client.commands.webcam_stream.base64.b64encode") as mock_b64:
            mock_buffer = MagicMock()
            mock_buffer.tobytes.return_value = b"frame_data"
            mock_encode.return_value = (True, mock_buffer)
            mock_b64.return_value = b"encoded_base64"

            result = self.command._encode_frame(mock_frame)

            assert result is not None
            assert result["encoding"] == "base64"
            assert result["format"] == "jpeg"
            assert result["width"] == 640
            assert result["height"] == 480

    def test_encode_frame_exception(self) -> None:
        mock_frame = MagicMock()
        mock_frame.shape = (480, 640, 3)

        with patch("client.commands.webcam_stream.cv2.imencode", side_effect=Exception("encode error")):
            result = self.command._encode_frame(mock_frame)
            assert result is None

    def test_stream_worker_camera_not_opened(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = False
            mock_vc.return_value = mock_cap

            result = self.command.execute({"action": "start"})

            time.sleep(0.1)

            assert self.command._running is False

    def test_stream_worker_read_failure(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            self.command.execute({"action": "start"})
            time.sleep(0.15)
            self.command._stop()

    def test_frame_buffer_limit(self) -> None:
        self.command._max_frames = 3
        mock_frame = MagicMock()
        mock_frame.shape = (480, 640, 3)

        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc, \
             patch("client.commands.webcam_stream.cv2.imencode") as mock_encode:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (True, mock_frame)
            mock_vc.return_value = mock_cap

            mock_encode.return_value = (True, MagicMock(tobytes=MagicMock(return_value=b"encoded")))

            self.command.execute({"action": "start", "fps": 60})
            time.sleep(0.2)
            self.command._stop()

            assert len(self.command._frames) <= self.command._max_frames

    def test_get_frame_with_data(self) -> None:
        mock_frame_data = {
            "data": "encoded_frame",
            "encoding": "base64",
            "format": "jpeg",
            "width": 640,
            "height": 480,
            "timestamp": time.time(),
            "frame_number": 0,
        }

        with self.command._frames_lock:
            self.command._frames.append(mock_frame_data)

        result = self.command.execute({"action": "get_frame"})

        assert result["success"] is True
        assert result["frame"] == mock_frame_data

    def test_get_frames_with_data(self) -> None:
        mock_frames = [
            {
                "data": f"frame_{i}",
                "encoding": "base64",
                "format": "jpeg",
                "width": 640,
                "height": 480,
                "timestamp": time.time(),
                "frame_number": i,
            }
            for i in range(3)
        ]

        with self.command._frames_lock:
            self.command._frames.extend(mock_frames)

        result = self.command.execute({"action": "get_frames"})

        assert result["success"] is True
        assert len(result["frames"]) == 3
        assert result["buffered_count"] == 3

    def test_multiple_start_stop_cycles(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            for cycle in range(3):
                start_result = self.command.execute({"action": "start"})
                assert start_result["success"] is True
                assert start_result["status"] == "started"

                status_result = self.command.execute({"action": "status"})
                assert status_result["status"] == "running"

                stop_result = self.command.execute({"action": "stop"})
                assert stop_result["success"] is True
                assert stop_result["status"] == "stopped"

    def test_elapsed_time_calculation(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            self.command.execute({"action": "start"})
            time.sleep(0.15)
            result = self.command.execute({"action": "stop"})

            assert "elapsed_time" in result
            assert result["elapsed_time"] >= 0.1

    def test_status_elapsed_time(self) -> None:
        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            self.command.execute({"action": "start"})
            time.sleep(0.1)
            result = self.command.execute({"action": "status"})

            assert "elapsed_time" in result
            assert result["elapsed_time"] >= 0.05

    def test_thread_safety_frame_access(self) -> None:
        import threading

        with patch("client.commands.webcam_stream.cv2.VideoCapture") as mock_vc:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (False, None)
            mock_vc.return_value = mock_cap

            self.command.execute({"action": "start"})

            def add_frames() -> None:
                for i in range(50):
                    frame_data = {
                        "data": f"frame_{threading.current_thread().name}_{i}",
                        "encoding": "base64",
                        "format": "jpeg",
                        "width": 640,
                        "height": 480,
                        "timestamp": time.time(),
                        "frame_number": i,
                    }
                    with self.command._frames_lock:
                        self.command._frames.append(frame_data)
                        if len(self.command._frames) > self.command._max_frames:
                            self.command._frames.pop(0)

            threads = [threading.Thread(target=add_frames) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            result = self.command.execute({"action": "get_frames"})
            assert result["success"] is True
            assert len(result["frames"]) <= self.command._max_frames

    def test_error_response(self) -> None:
        result = self.command._error_response("Test error")
        assert result["success"] is False
        assert result["error"] == "Test error"
