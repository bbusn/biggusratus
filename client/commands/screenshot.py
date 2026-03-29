import base64
import io
import logging
from typing import Any, Dict, List

from mss import mss
from PIL import Image

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)


class ScreenshotCommand(BaseCommand):

    @property
    def name(self) -> str:
        return "screenshot"

    @property
    def description(self) -> str:
        return "Capture screen"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        monitor_index = params.get("monitor", -1)
        if not isinstance(monitor_index, int):
            monitor_index = -1

        format_type = params.get("format", "png")
        if format_type not in ("png", "jpeg"):
            format_type = "png"

        try:
            with mss() as sct:
                monitors = sct.monitors

                if not monitors:
                    return self._error_response("No monitors detected")

                if monitor_index == -1:
                    return self._capture_all_monitors(sct, monitors, format_type)
                else:
                    return self._capture_single_monitor(sct, monitor_index, format_type)

        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return self._error_response(f"Failed to capture screenshot: {e}")

    def _capture_single_monitor(
        self, sct: mss, monitor_index: int, format_type: str
    ) -> Dict[str, Any]:
        monitors = sct.monitors

        if monitor_index < 0 or monitor_index >= len(monitors):
            return self._error_response(
                f"Invalid monitor index {monitor_index}. Available: 0-{len(monitors) - 1}"
            )

        monitor = monitors[monitor_index]
        screenshot = sct.grab(monitor)

        output = io.BytesIO()
        if format_type == "jpeg":
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            img.save(output, format="JPEG", quality=85)
        else:
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            img.save(output, format="PNG")

        encoded = base64.b64encode(output.getvalue()).decode("utf-8")

        logger.info(
            f"Screenshot captured: monitor {monitor_index}, "
            f"{screenshot.size[0]}x{screenshot.size[1]}, {len(encoded)} bytes encoded"
        )

        return {
            "success": True,
            "image_data": encoded,
            "encoding": "base64",
            "format": format_type,
            "monitor": monitor_index,
            "width": screenshot.size[0],
            "height": screenshot.size[1],
            "message": f"Screenshot captured from monitor {monitor_index}",
        }

    def _capture_all_monitors(
        self, sct: mss, monitors: List[Dict[str, int]], format_type: str
    ) -> Dict[str, Any]:
        screenshots = []

        for i, monitor in enumerate(monitors):
            screenshot = sct.grab(monitor)

            output = io.BytesIO()
            if format_type == "jpeg":
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                img.save(output, format="JPEG", quality=85)
            else:
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                img.save(output, format="PNG")

            encoded = base64.b64encode(output.getvalue()).decode("utf-8")

            screenshots.append({
                "monitor": i,
                "image_data": encoded,
                "width": screenshot.size[0],
                "height": screenshot.size[1],
            })

            logger.info(
                f"Screenshot captured: monitor {i}, "
                f"{screenshot.size[0]}x{screenshot.size[1]}"
            )

        return {
            "success": True,
            "screenshots": screenshots,
            "count": len(screenshots),
            "encoding": "base64",
            "format": format_type,
            "message": f"Captured {len(screenshots)} monitor(s)",
        }

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": message,
        }
