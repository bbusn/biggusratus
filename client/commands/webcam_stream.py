import base64
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import cv2

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)


class WebcamStreamCommand(BaseCommand):
    _instance: Optional["WebcamStreamCommand"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "WebcamStreamCommand":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._stream_thread: Optional[threading.Thread] = None
        self._stream_lock = threading.Lock()
        self._running = False
        self._camera_index = 0
        self._fps = 15
        self._quality = 70
        self._frame_count = 0
        self._start_time: Optional[float] = None
        self._frames: List[Dict[str, Any]] = []
        self._frames_lock = threading.Lock()
        self._max_frames = 30

    @property
    def name(self) -> str:
        return "webcam_stream"

    @property
    def description(self) -> str:
        return "Stream webcam video"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action", "").lower()

        if action == "start":
            return self._start(params)
        elif action == "stop":
            return self._stop()
        elif action == "get_frame":
            return self._get_frame()
        elif action == "get_frames":
            return self._get_frames()
        elif action == "status":
            return self._status()
        else:
            return self._error_response(
                f"Invalid action '{action}'. Use: start, stop, get_frame, get_frames, or status"
            )

    def _start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        with self._stream_lock:
            if self._running:
                return {
                    "success": True,
                    "status": "already_running",
                    "message": "Webcam stream is already running",
                    "camera": self._camera_index,
                    "fps": self._fps,
                    "frame_count": self._frame_count,
                }

            self._camera_index = params.get("camera", 0)
            if not isinstance(self._camera_index, int):
                self._camera_index = 0

            self._fps = params.get("fps", 15)
            if not isinstance(self._fps, int) or self._fps < 1 or self._fps > 60:
                self._fps = 15

            self._quality = params.get("quality", 70)
            if not isinstance(self._quality, int) or self._quality < 1 or self._quality > 100:
                self._quality = 70

            with self._frames_lock:
                self._frames.clear()
            self._frame_count = 0
            self._start_time = time.time()
            self._running = True

            self._stream_thread = threading.Thread(target=self._stream_worker, daemon=True)
            self._stream_thread.start()

            logger.info(f"Webcam stream started: camera {self._camera_index}, {self._fps} fps")

            return {
                "success": True,
                "status": "started",
                "message": f"Webcam stream started on camera {self._camera_index}",
                "camera": self._camera_index,
                "fps": self._fps,
                "quality": self._quality,
                "timestamp": time.time(),
            }

    def _stop(self) -> Dict[str, Any]:
        with self._stream_lock:
            if not self._running:
                return {
                    "success": True,
                    "status": "not_running",
                    "message": "Webcam stream was not running",
                }

            self._running = False

            if self._stream_thread is not None:
                self._stream_thread.join(timeout=2.0)
                self._stream_thread = None

            elapsed = time.time() - self._start_time if self._start_time else 0
            logger.info(f"Webcam stream stopped. Captured {self._frame_count} frames in {elapsed:.2f}s")

            return {
                "success": True,
                "status": "stopped",
                "message": f"Webcam stream stopped. Captured {self._frame_count} frames",
                "frame_count": self._frame_count,
                "elapsed_time": round(elapsed, 2),
            }

    def _get_frame(self) -> Dict[str, Any]:
        with self._frames_lock:
            if not self._frames:
                return {
                    "success": False,
                    "error": "No frames available",
                    "status": "running" if self._running else "stopped",
                }

            frame = self._frames[-1]
            return {
                "success": True,
                "status": "running" if self._running else "stopped",
                "frame": frame,
                "frame_count": self._frame_count,
            }

    def _get_frames(self) -> Dict[str, Any]:
        with self._frames_lock:
            frames = list(self._frames)

        return {
            "success": True,
            "status": "running" if self._running else "stopped",
            "frames": frames,
            "frame_count": self._frame_count,
            "buffered_count": len(frames),
        }

    def _status(self) -> Dict[str, Any]:
        elapsed = 0.0
        if self._start_time:
            elapsed = time.time() - self._start_time

        return {
            "success": True,
            "status": "running" if self._running else "stopped",
            "camera": self._camera_index,
            "fps": self._fps,
            "quality": self._quality,
            "frame_count": self._frame_count,
            "elapsed_time": round(elapsed, 2),
            "buffered_frames": len(self._frames),
        }

    def _stream_worker(self) -> None:
        cap: Optional[cv2.VideoCapture] = None

        try:
            cap = cv2.VideoCapture(self._camera_index)
            if not cap.isOpened():
                logger.error(f"Cannot open camera {self._camera_index}")
                self._running = False
                return

            cap.set(cv2.CAP_PROP_FPS, self._fps)

            frame_interval = 1.0 / self._fps

            while self._running:
                frame_start = time.time()

                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame from camera")
                    time.sleep(0.1)
                    continue

                encoded_frame = self._encode_frame(frame)
                if encoded_frame:
                    with self._frames_lock:
                        self._frames.append(encoded_frame)
                        if len(self._frames) > self._max_frames:
                            self._frames.pop(0)
                    self._frame_count += 1

                elapsed = time.time() - frame_start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception as e:
            logger.error(f"Stream worker error: {e}")
        finally:
            if cap is not None:
                cap.release()
            self._running = False

    def _encode_frame(self, frame: Any) -> Optional[Dict[str, Any]]:
        try:
            height, width = frame.shape[:2]
            _, buffer = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._quality]
            )
            encoded = base64.b64encode(buffer.tobytes()).decode("utf-8")

            return {
                "data": encoded,
                "encoding": "base64",
                "format": "jpeg",
                "width": width,
                "height": height,
                "timestamp": time.time(),
                "frame_number": self._frame_count,
            }
        except Exception as e:
            logger.error(f"Frame encoding error: {e}")
            return None

    def get_available_cameras(self) -> List[int]:
        available = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": message,
        }
