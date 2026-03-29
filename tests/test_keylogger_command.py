import time
from datetime import datetime
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from client.commands.keylogger import KeyloggerCommand


class TestKeyloggerCommand:
    def setup_method(self) -> None:
        KeyloggerCommand._instance = None
        self.command = KeyloggerCommand()

    def teardown_method(self) -> None:
        if self.command._running:
            self.command._stop()

    def test_name_property(self) -> None:
        assert self.command.name == "keylogger"

    def test_description_property(self) -> None:
        assert "keystroke" in self.command.description.lower()

    def test_singleton_pattern(self) -> None:
        command2 = KeyloggerCommand()
        assert command2 is self.command

    def test_execute_invalid_action(self) -> None:
        result = self.command.execute({"action": "invalid"})
        assert result["success"] is False
        assert "Invalid action" in result["error"]

    def test_execute_missing_action(self) -> None:
        result = self.command.execute({})
        assert result["success"] is False
        assert "Invalid action" in result["error"]

    def test_start_keylogger(self) -> None:
        with patch("client.commands.keylogger.keyboard.Listener") as mock_listener:
            mock_listener_instance = MagicMock()
            mock_listener.return_value = mock_listener_instance

            result = self.command.execute({"action": "start"})

            assert result["success"] is True
            assert result["status"] == "started"
            mock_listener.assert_called_once()
            mock_listener_instance.start.assert_called_once()

    def test_start_already_running(self) -> None:
        with patch("client.commands.keylogger.keyboard.Listener") as mock_listener:
            mock_listener_instance = MagicMock()
            mock_listener.return_value = mock_listener_instance

            self.command.execute({"action": "start"})
            result = self.command.execute({"action": "start"})

            assert result["success"] is True
            assert result["status"] == "already_running"

    def test_stop_keylogger(self) -> None:
        with patch("client.commands.keylogger.keyboard.Listener") as mock_listener:
            mock_listener_instance = MagicMock()
            mock_listener.return_value = mock_listener_instance

            self.command.execute({"action": "start"})
            result = self.command.execute({"action": "stop"})

            assert result["success"] is True
            assert result["status"] == "stopped"
            mock_listener_instance.stop.assert_called_once()

    def test_stop_not_running(self) -> None:
        result = self.command.execute({"action": "stop"})
        assert result["success"] is True
        assert result["status"] == "not_running"

    def test_get_keystrokes_empty(self) -> None:
        result = self.command.execute({"action": "get"})
        assert result["success"] is True
        assert result["count"] == 0
        assert result["keystrokes"] == []

    def test_get_keystrokes_with_data(self) -> None:
        with patch("client.commands.keylogger.keyboard.Listener") as mock_listener:
            mock_listener_instance = MagicMock()
            mock_listener.return_value = mock_listener_instance

            self.command.execute({"action": "start"})

            mock_char_key = MagicMock()
            mock_char_key.char = "a"
            mock_char_key.vk = None

            mock_char_key2 = MagicMock()
            mock_char_key2.char = "b"
            mock_char_key2.vk = None

            mock_special_key = MagicMock()
            mock_special_key.name = "enter"

            with patch("client.commands.keylogger.isinstance") as mock_isinstance:
                def isinstance_side_effect(obj, cls):
                    if obj is mock_char_key or obj is mock_char_key2:
                        from pynput.keyboard import KeyCode
                        return cls == KeyCode
                    elif obj is mock_special_key:
                        from pynput.keyboard import Key
                        return cls == Key
                    return False

                mock_isinstance.side_effect = isinstance_side_effect

                self.command._on_press(mock_char_key)
                self.command._on_press(mock_char_key2)
                self.command._on_press(mock_special_key)

            result = self.command.execute({"action": "get"})

            assert result["success"] is True
            assert result["count"] == 3
            assert len(result["keystrokes"]) == 3

            keys = [k["key"] for k in result["keystrokes"]]
            assert "a" in keys
            assert "b" in keys
            assert "[enter]" in keys

    def test_on_press_regular_key(self) -> None:
        mock_key = MagicMock()
        mock_key.char = "x"
        mock_key.vk = None

        with patch("client.commands.keylogger.isinstance") as mock_isinstance:
            from pynput.keyboard import KeyCode
            mock_isinstance.side_effect = lambda obj, cls: obj is mock_key and cls == KeyCode

            self.command._on_press(mock_key)

        with self.command._keystroke_lock:
            assert len(self.command._keystrokes) == 1
            assert self.command._keystrokes[0]["key"] == "x"
            assert "timestamp" in self.command._keystrokes[0]
            assert "datetime" in self.command._keystrokes[0]

    def test_on_press_special_key(self) -> None:
        mock_key = MagicMock()
        mock_key.name = "shift"

        with patch("client.commands.keylogger.isinstance") as mock_isinstance:
            from pynput.keyboard import Key
            mock_isinstance.side_effect = lambda obj, cls: obj is mock_key and cls == Key

            self.command._on_press(mock_key)

        with self.command._keystroke_lock:
            assert len(self.command._keystrokes) == 1
            assert self.command._keystrokes[0]["key"] == "[shift]"

    def test_on_press_keycode_no_char(self) -> None:
        mock_key = MagicMock()
        mock_key.char = None
        mock_key.vk = 65

        with patch("client.commands.keylogger.isinstance") as mock_isinstance:
            from pynput.keyboard import KeyCode
            mock_isinstance.side_effect = lambda obj, cls: obj is mock_key and cls == KeyCode

            self.command._on_press(mock_key)

        with self.command._keystroke_lock:
            assert len(self.command._keystrokes) == 1
            assert "[KeyCode:65]" in self.command._keystrokes[0]["key"]

    def test_on_press_exception_handling(self) -> None:
        problematic_key = MagicMock()
        problematic_key.char = None
        problematic_key.vk = None
        del problematic_key.name

        with patch("client.commands.keylogger.isinstance", return_value=False):
            self.command._on_press(problematic_key)

        with self.command._keystroke_lock:
            assert len(self.command._keystrokes) == 1
            assert "MagicMock" in self.command._keystrokes[0]["key"]

    def test_keystroke_timestamp_format(self) -> None:
        mock_key = MagicMock()
        mock_key.char = "a"

        with patch("client.commands.keylogger.isinstance") as mock_isinstance:
            from pynput.keyboard import KeyCode
            mock_isinstance.side_effect = lambda obj, cls: obj is mock_key and cls == KeyCode

            before = time.time()
            self.command._on_press(mock_key)
            after = time.time()

        with self.command._keystroke_lock:
            keystroke = self.command._keystrokes[0]
            assert before <= keystroke["timestamp"] <= after
            assert "datetime" in keystroke
            assert "T" in keystroke["datetime"]

    def test_keystrokes_cleared_on_start(self) -> None:
        mock_key = MagicMock()
        mock_key.char = "a"

        with patch("client.commands.keylogger.isinstance") as mock_isinstance:
            from pynput.keyboard import KeyCode
            mock_isinstance.side_effect = lambda obj, cls: obj is mock_key and cls == KeyCode

            self.command._on_press(mock_key)
            assert self.command._get_keystroke_count() == 1

        with patch("client.commands.keylogger.keyboard.Listener") as mock_listener:
            mock_listener_instance = MagicMock()
            mock_listener.return_value = mock_listener_instance

            self.command.execute({"action": "start"})

            assert self.command._get_keystroke_count() == 0

    def test_thread_safety_keystroke_access(self) -> None:
        import threading

        with patch("client.commands.keylogger.keyboard.Listener") as mock_listener:
            mock_listener_instance = MagicMock()
            mock_listener.return_value = mock_listener_instance

            self.command.execute({"action": "start"})

            def add_keystrokes() -> None:
                for i in range(100):
                    with self.command._keystroke_lock:
                        self.command._keystrokes.append({
                            "timestamp": time.time(),
                            "datetime": datetime.fromtimestamp(time.time()).isoformat(),
                            "key": f"key_{threading.current_thread().name}_{i}",
                        })

            threads = [threading.Thread(target=add_keystrokes) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            result = self.command.execute({"action": "get"})
            assert result["count"] == 500

    def test_multiple_start_stop_cycles(self) -> None:
        with patch("client.commands.keylogger.keyboard.Listener") as mock_listener:
            for cycle in range(3):
                mock_listener_instance = MagicMock()
                mock_listener.return_value = mock_listener_instance

                start_result = self.command.execute({"action": "start"})
                assert start_result["success"] is True

                mock_key = MagicMock()
                mock_key.char = str(cycle)

                with patch("client.commands.keylogger.isinstance") as mock_isinstance:
                    from pynput.keyboard import KeyCode
                    mock_isinstance.side_effect = lambda obj, cls, c=cycle: obj is mock_key and cls == KeyCode
                    self.command._on_press(mock_key)

                stop_result = self.command.execute({"action": "stop"})
                assert stop_result["success"] is True

                get_result = self.command.execute({"action": "get"})
                assert get_result["count"] == 1

    def test_get_keystroke_count(self) -> None:
        mock_key = MagicMock()
        mock_key.char = "a"

        with patch("client.commands.keylogger.isinstance") as mock_isinstance:
            from pynput.keyboard import KeyCode
            mock_isinstance.side_effect = lambda obj, cls: obj is mock_key and cls == KeyCode

            self.command._on_press(mock_key)
            self.command._on_press(mock_key)
            self.command._on_press(mock_key)

        count = self.command._get_keystroke_count()
        assert count == 3
