import base64
from typing import Any, Tuple
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from client.commands.webcam import WebcamSnapshotCommand


class TestWebcamSnapshotCommand:
    def setup_method(self) -> None:
        self.command = WebcamSnapshotCommand()

    def test_name_property(self) -> None:
        assert self.command.name == "webcam_snapshot"

    def test_description_property(self) -> None:
        assert "webcam" in self.command.description.lower()
        assert "photo" in self.command.description.lower()

    def test_execute_default_camera_png(self) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cap.release.return_value = None

        with patch("client.commands.webcam.cv2.VideoCapture", return_value=mock_cap):
            with patch("client.commands.webcam.cv2.imencode") as mock_encode:
                mock_encode.return_value = (True, np.array([1, 2, 3, 4], dtype=np.uint8))

                result = self.command.execute({})

        assert result["success"] is True
        assert result["encoding"] == "base64"
        assert result["format"] == "png"
        assert result["camera"] == 0
        assert "image_data" in result
        assert "width" in result
        assert "height" in result

    def test_execute_specific_camera(self) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cap.release.return_value = None

        with patch("client.commands.webcam.cv2.VideoCapture", return_value=mock_cap):
            with patch("client.commands.webcam.cv2.imencode") as mock_encode:
                mock_encode.return_value = (True, np.array([1, 2, 3, 4], dtype=np.uint8))

                result = self.command.execute({"camera": 1})

        assert result["success"] is True
        assert result["camera"] == 1

    def test_execute_jpeg_format(self) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cap.release.return_value = None

        with patch("client.commands.webcam.cv2.VideoCapture", return_value=mock_cap):
            with patch("client.commands.webcam.cv2.imencode") as mock_encode:
                mock_encode.return_value = (True, np.array([1, 2, 3, 4], dtype=np.uint8))

                result = self.command.execute({"format": "jpeg"})

        assert result["success"] is True
        assert result["format"] == "jpeg"

    def test_execute_invalid_format_defaults_to_png(self) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cap.release.return_value = None

        with patch("client.commands.webcam.cv2.VideoCapture", return_value=mock_cap):
            with patch("client.commands.webcam.cv2.imencode") as mock_encode:
                mock_encode.return_value = (True, np.array([1, 2, 3, 4], dtype=np.uint8))

                result = self.command.execute({"format": "invalid"})

        assert result["success"] is True
        assert result["format"] == "png"

    def test_execute_invalid_camera_type_uses_default(self) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cap.release.return_value = None

        with patch("client.commands.webcam.cv2.VideoCapture", return_value=mock_cap):
            with patch("client.commands.webcam.cv2.imencode") as mock_encode:
                mock_encode.return_value = (True, np.array([1, 2, 3, 4], dtype=np.uint8))

                result = self.command.execute({"camera": "invalid"})

        assert result["success"] is True
        assert result["camera"] == 0

    def test_execute_camera_not_opened(self) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cap.release.return_value = None

        with patch("client.commands.webcam.cv2.VideoCapture", return_value=mock_cap):
            result = self.command.execute({"camera": 0})

        assert result["success"] is False
        assert "Cannot open camera" in result["error"]

    def test_execute_frame_capture_failed(self) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, np.array([]))
        mock_cap.release.return_value = None

        with patch("client.commands.webcam.cv2.VideoCapture", return_value=mock_cap):
            result = self.command.execute({"camera": 0})

        assert result["success"] is False
        assert "Failed to capture frame" in result["error"]

    def test_execute_exception_handling(self) -> None:
        with patch("client.commands.webcam.cv2.VideoCapture") as mock_vc:
            mock_vc.side_effect = Exception("Camera error")

            result = self.command.execute({"camera": 0})

        assert result["success"] is False
        assert "Failed to capture webcam snapshot" in result["error"]

    def test_get_available_cameras(self) -> None:
        available_indices = [0, 2]

        def create_mock_camera(idx: int) -> MagicMock:
            mock = MagicMock()
            mock.isOpened.return_value = idx in available_indices
            mock.release.return_value = None
            return mock

        with patch("client.commands.webcam.cv2.VideoCapture") as mock_vc:
            mock_vc.side_effect = create_mock_camera
            result = self.command.get_available_cameras()

        assert result == available_indices

    def test_execute_with_real_frame_encoding(self) -> None:
        mock_cap = MagicMock()
        test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, test_frame)
        mock_cap.release.return_value = None

        with patch("client.commands.webcam.cv2.VideoCapture", return_value=mock_cap):
            result = self.command.execute({})

        assert result["success"] is True
        assert result["width"] == 640
        assert result["height"] == 480

        img_data = base64.b64decode(result["image_data"])
        assert len(img_data) > 0

    def test_get_available_cameras_empty(self) -> None:
        def create_mock_camera(idx: int) -> MagicMock:
            mock = MagicMock()
            mock.isOpened.return_value = False
            mock.release.return_value = None
            return mock

        with patch("client.commands.webcam.cv2.VideoCapture") as mock_vc:
            mock_vc.side_effect = create_mock_camera
            result = self.command.get_available_cameras()

        assert result == []
