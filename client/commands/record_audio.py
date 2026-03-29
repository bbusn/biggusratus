import base64
import io
import logging
import threading
import time
import wave
from typing import Any, Dict, List, Optional

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    pyaudio = None
    PYAUDIO_AVAILABLE = False
    logger.warning("PyAudio not available. Audio recording will not work.")


class RecordAudioCommand(BaseCommand):
    _instance: Optional["RecordAudioCommand"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "RecordAudioCommand":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._recording = False
        self._audio: Optional[Any] = None
        self._stream: Optional[Any] = None
        self._record_thread: Optional[threading.Thread] = None
        self._frames: List[bytes] = []
        self._frames_lock = threading.Lock()
        self._sample_rate = 44100
        self._channels = 1
        self._chunk_size = 1024
        self._start_time: Optional[float] = None
        self._duration: Optional[float] = None

    @property
    def name(self) -> str:
        return "record_audio"

    @property
    def description(self) -> str:
        return "Record from microphone"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not PYAUDIO_AVAILABLE:
            return self._error_response("PyAudio is not available. Cannot record audio.")

        action = params.get("action", "").lower()

        if action == "start":
            return self._start(params)
        elif action == "stop":
            return self._stop()
        elif action == "status":
            return self._status()
        elif action == "record":
            return self._record_fixed_duration(params)
        else:
            return self._error_response(
                f"Invalid action '{action}'. Use: start, stop, status, or record"
            )

    def _start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if self._recording:
                elapsed = time.time() - self._start_time if self._start_time else 0
                return {
                    "success": True,
                    "status": "already_recording",
                    "message": "Audio recording is already in progress",
                    "elapsed_time": round(elapsed, 2),
                }

            self._sample_rate = params.get("sample_rate", 44100)
            if not isinstance(self._sample_rate, int) or self._sample_rate < 8000:
                self._sample_rate = 44100

            self._channels = params.get("channels", 1)
            if self._channels not in (1, 2):
                self._channels = 1

            self._duration = params.get("duration")
            if self._duration is not None:
                if not isinstance(self._duration, (int, float)) or self._duration <= 0:
                    self._duration = None

            with self._frames_lock:
                self._frames.clear()

            try:
                self._audio = pyaudio.PyAudio()
                self._stream = self._audio.open(
                    format=pyaudio.paInt16,
                    channels=self._channels,
                    rate=self._sample_rate,
                    input=True,
                    frames_per_buffer=self._chunk_size,
                )
            except Exception as e:
                logger.error(f"Failed to initialize audio: {e}")
                self._cleanup()
                return self._error_response(f"Failed to initialize audio: {e}")

            self._recording = True
            self._start_time = time.time()

            self._record_thread = threading.Thread(target=self._record_worker, daemon=True)
            self._record_thread.start()

            logger.info(f"Audio recording started: {self._sample_rate}Hz, {self._channels} channel(s)")

            return {
                "success": True,
                "status": "started",
                "message": "Audio recording started",
                "sample_rate": self._sample_rate,
                "channels": self._channels,
                "duration": self._duration,
                "timestamp": self._start_time,
            }

    def _stop(self) -> Dict[str, Any]:
        with self._lock:
            if not self._recording:
                return {
                    "success": True,
                    "status": "not_recording",
                    "message": "Audio recording was not in progress",
                }

            self._recording = False

            if self._record_thread is not None:
                self._record_thread.join(timeout=2.0)
                self._record_thread = None

            elapsed = time.time() - self._start_time if self._start_time else 0

            wav_data = self._create_wav()

            self._cleanup()

            logger.info(f"Audio recording stopped. Duration: {elapsed:.2f}s")

            result: Dict[str, Any] = {
                "success": True,
                "status": "stopped",
                "message": f"Audio recording stopped. Duration: {elapsed:.2f}s",
                "elapsed_time": round(elapsed, 2),
            }

            if wav_data:
                result["audio_data"] = wav_data
                result["encoding"] = "base64"
                result["format"] = "wav"

            return result

    def _status(self) -> Dict[str, Any]:
        elapsed = 0.0
        if self._start_time and self._recording:
            elapsed = time.time() - self._start_time

        return {
            "success": True,
            "status": "recording" if self._recording else "stopped",
            "sample_rate": self._sample_rate if self._recording else None,
            "channels": self._channels if self._recording else None,
            "elapsed_time": round(elapsed, 2),
            "duration_limit": self._duration,
        }

    def _record_fixed_duration(self, params: Dict[str, Any]) -> Dict[str, Any]:
        duration = params.get("duration", 5)
        if not isinstance(duration, (int, float)) or duration <= 0:
            duration = 5

        start_result = self._start(params)
        if not start_result.get("success"):
            return start_result

        time.sleep(duration)

        return self._stop()

    def _record_worker(self) -> None:
        target_duration = self._duration

        try:
            while self._recording:
                if target_duration is not None and self._start_time:
                    elapsed = time.time() - self._start_time
                    if elapsed >= target_duration:
                        logger.info(f"Target duration {target_duration}s reached")
                        break

                try:
                    if self._stream is not None:
                        data = self._stream.read(self._chunk_size, exception_on_overflow=False)
                        with self._frames_lock:
                            self._frames.append(data)
                except OSError as e:
                    logger.error(f"Error reading audio stream: {e}")
                    break
                except Exception as e:
                    logger.error(f"Unexpected error in recording: {e}")
                    break

        finally:
            if target_duration is not None and self._recording:
                self._recording = False

    def _create_wav(self) -> Optional[str]:
        with self._frames_lock:
            frames = list(self._frames)

        if not frames:
            return None

        try:
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav_file:
                wav_file.setnchannels(self._channels)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self._sample_rate)
                wav_file.writeframes(b"".join(frames))

            wav_bytes = buffer.getvalue()
            encoded = base64.b64encode(wav_bytes).decode("utf-8")

            logger.info(f"WAV data created: {len(wav_bytes)} bytes, {len(encoded)} chars encoded")
            return encoded

        except Exception as e:
            logger.error(f"Error creating WAV: {e}")
            return None

    def _cleanup(self) -> None:
        try:
            if self._stream is not None:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception as e:
                    logger.error(f"Error closing stream: {e}")
                self._stream = None

            if self._audio is not None:
                try:
                    self._audio.terminate()
                except Exception as e:
                    logger.error(f"Error terminating audio: {e}")
                self._audio = None

            with self._frames_lock:
                self._frames.clear()

            self._start_time = None

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def get_available_devices(self) -> List[Dict[str, Any]]:
        if not PYAUDIO_AVAILABLE:
            return []

        devices = []
        try:
            audio = pyaudio.PyAudio()
            for i in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    devices.append({
                        "index": i,
                        "name": info.get("name", "Unknown"),
                        "channels": info.get("maxInputChannels", 0),
                        "sample_rate": info.get("defaultSampleRate", 0),
                    })
            audio.terminate()
        except Exception as e:
            logger.error(f"Error getting devices: {e}")

        return devices

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": message,
        }
