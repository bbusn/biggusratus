import base64
from io import BytesIO
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from client.commands.screenshot import ScreenshotCommand


class MockMonitor:
    def __init__(self, width: int, height: int):
        self.size = (width, height)
        self.rgb = b"\x00" * (width * height * 3)


class MockMSS:
    def __init__(self, monitor_count: int = 2):
        self._monitor_count = monitor_count
        self.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080} for _ in range(monitor_count)]

    def __enter__(self):
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def grab(self, monitor: Dict[str, int]) -> MockMonitor:
        return MockMonitor(monitor["width"], monitor["height"])


class TestScreenshotCommand:
    def setup_method(self) -> None:
        self.command = ScreenshotCommand()

    def test_name_property(self) -> None:
        assert self.command.name == "screenshot"

    def test_description_property(self) -> None:
        assert "capture" in self.command.description.lower()
        assert "screen" in self.command.description.lower()

    def test_execute_single_monitor_png(self) -> None:
        mock_mss = MockMSS(monitor_count=2)
        with patch("client.commands.screenshot.mss", return_value=MockMSS):
            with patch("client.commands.screenshot.mss") as mss_mock:
                mss_mock.return_value.__enter__ = lambda self: mock_mss
                mss_mock.return_value.__exit__ = lambda self, *args: None
                mss_mock.return_value.monitors = mock_mss.monitors
                mss_mock.return_value.grab = mock_mss.grab

                result = self.command.execute({"monitor": 0})

        assert result["success"] is True
        assert result["encoding"] == "base64"
        assert result["format"] == "png"
        assert result["monitor"] == 0
        assert "image_data" in result
        assert "width" in result
        assert "height" in result

        img_data = base64.b64decode(result["image_data"])
        img = Image.open(BytesIO(img_data))
        assert img.format == "PNG"

    def test_execute_single_monitor_jpeg(self) -> None:
        mock_mss = MockMSS(monitor_count=2)
        with patch("client.commands.screenshot.mss") as mss_mock:
            mss_mock.return_value.__enter__ = lambda self: mock_mss
            mss_mock.return_value.__exit__ = lambda self, *args: None
            mss_mock.return_value.monitors = mock_mss.monitors
            mss_mock.return_value.grab = mock_mss.grab

            result = self.command.execute({"monitor": 0, "format": "jpeg"})

        assert result["success"] is True
        assert result["format"] == "jpeg"

        img_data = base64.b64decode(result["image_data"])
        img = Image.open(BytesIO(img_data))
        assert img.format == "JPEG"

    def test_execute_all_monitors(self) -> None:
        mock_mss = MockMSS(monitor_count=3)
        with patch("client.commands.screenshot.mss") as mss_mock:
            mss_mock.return_value.__enter__ = lambda self: mock_mss
            mss_mock.return_value.__exit__ = lambda self, *args: None
            mss_mock.return_value.monitors = mock_mss.monitors
            mss_mock.return_value.grab = mock_mss.grab

            result = self.command.execute({"monitor": -1})

        assert result["success"] is True
        assert result["encoding"] == "base64"
        assert "screenshots" in result
        assert result["count"] == 3
        assert len(result["screenshots"]) == 3
        assert "message" in result

        for i, screenshot in enumerate(result["screenshots"]):
            assert screenshot["monitor"] == i
            assert "image_data" in screenshot
            assert "width" in screenshot
            assert "height" in screenshot

    def test_execute_invalid_monitor_index(self) -> None:
        mock_mss = MockMSS(monitor_count=2)
        with patch("client.commands.screenshot.mss") as mss_mock:
            mss_mock.return_value.__enter__ = lambda self: mock_mss
            mss_mock.return_value.__exit__ = lambda self, *args: None
            mss_mock.return_value.monitors = mock_mss.monitors
            mss_mock.return_value.grab = mock_mss.grab

            result = self.command.execute({"monitor": 10})

        assert result["success"] is False
        assert "Invalid monitor index" in result["error"]

    def test_execute_invalid_format_defaults_to_png(self) -> None:
        mock_mss = MockMSS(monitor_count=2)
        with patch("client.commands.screenshot.mss") as mss_mock:
            mss_mock.return_value.__enter__ = lambda self: mock_mss
            mss_mock.return_value.__exit__ = lambda self, *args: None
            mss_mock.return_value.monitors = mock_mss.monitors
            mss_mock.return_value.grab = mock_mss.grab

            result = self.command.execute({"monitor": 0, "format": "invalid"})

        assert result["success"] is True
        assert result["format"] == "png"

    def test_execute_default_parameters(self) -> None:
        mock_mss = MockMSS(monitor_count=2)
        with patch("client.commands.screenshot.mss") as mss_mock:
            mss_mock.return_value.__enter__ = lambda self: mock_mss
            mss_mock.return_value.__exit__ = lambda self, *args: None
            mss_mock.return_value.monitors = mock_mss.monitors
            mss_mock.return_value.grab = mock_mss.grab

            result = self.command.execute({})

        assert result["success"] is True
        assert result["encoding"] == "base64"
        assert "screenshots" in result

    def test_execute_invalid_monitor_type_uses_default(self) -> None:
        mock_mss = MockMSS(monitor_count=2)
        with patch("client.commands.screenshot.mss") as mss_mock:
            mss_mock.return_value.__enter__ = lambda self: mock_mss
            mss_mock.return_value.__exit__ = lambda self, *args: None
            mss_mock.return_value.monitors = mock_mss.monitors
            mss_mock.return_value.grab = mock_mss.grab

            result = self.command.execute({"monitor": "invalid"})

        assert result["success"] is True
        assert "screenshots" in result

    def test_execute_no_monitors_error(self) -> None:
        mock_mss = MagicMock()
        mock_mss.__enter__ = MagicMock(return_value=mock_mss)
        mock_mss.__exit__ = MagicMock(return_value=None)
        mock_mss.monitors = []

        with patch("client.commands.screenshot.mss", return_value=mock_mss):
            result = self.command.execute({"monitor": 0})

        assert result["success"] is False
        assert "No monitors" in result["error"]

    def test_execute_screenshot_exception(self) -> None:
        with patch("client.commands.screenshot.mss") as mss_mock:
            mss_mock.side_effect = Exception("Screenshot failed")

            result = self.command.execute({"monitor": 0})

        assert result["success"] is False
        assert "Failed to capture screenshot" in result["error"]
