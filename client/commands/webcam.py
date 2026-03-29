import base64
import io
import logging
from typing import Any, Dict, List

import cv2

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)


class WebcamSnapshotCommand(BaseCommand):

    @property
    def name(self) -> str:
        return "webcam_snapshot"

    @property
    def description(self) -> str:
        return "Take webcam photo"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        camera_index = params.get("camera", 0)
        if not isinstance(camera_index, int):
            camera_index = 0

        format_type = params.get("format", "png")
        if format_type not in ("png", "jpeg"):
            format_type = "png"

        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                return self._error_response(
                    f"Cannot open camera {camera_index}. Camera may be in use or not connected."
                )

            ret, frame = cap.read()
            cap.release()

            if not ret:
                return self._error_response(f"Failed to capture frame from camera {camera_index}")

            return self._encode_frame(frame, camera_index, format_type)

        except Exception as e:
            logger.error(f"Webcam snapshot error: {e}")
            return self._error_response(f"Failed to capture webcam snapshot: {e}")

    def get_available_cameras(self) -> List[int]:
        available = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available

    def _encode_frame(
        self, frame: Any, camera_index: int, format_type: str
    ) -> Dict[str, Any]:
        height, width = frame.shape[:2]

        if format_type == "jpeg":
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        else:
            _, buffer = cv2.imencode(".png", frame)

        encoded = base64.b64encode(buffer.tobytes()).decode("utf-8")

        logger.info(
            f"Webcam snapshot captured: camera {camera_index}, "
            f"{width}x{height}, {len(encoded)} bytes encoded"
        )

        return {
            "success": True,
            "image_data": encoded,
            "encoding": "base64",
            "format": format_type,
            "camera": camera_index,
            "width": width,
            "height": height,
            "message": f"Webcam snapshot captured from camera {camera_index}",
        }

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": message,
        }
