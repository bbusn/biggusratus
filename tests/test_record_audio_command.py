import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from client.commands.record_audio import RecordAudioCommand


class TestRecordAudioCommand:
    def setup_method(self) -> None:
        RecordAudioCommand._instance = None
        self.command = RecordAudioCommand()

    def teardown_method(self) -> None:
        if self.command._recording:
            self.command._recording = False
            self.command._cleanup()

    def test_name_property(self) -> None:
        assert self.command.name == "record_audio"

    def test_description_property(self) -> None:
        assert "record" in self.command.description.lower()
        assert "microphone" in self.command.description.lower()

    def test_singleton_pattern(self) -> None:
        command2 = RecordAudioCommand()
        assert command2 is self.command

    def test_execute_invalid_action(self) -> None:
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True):
            result = self.command.execute({"action": "invalid"})
            assert result["success"] is False
            assert "Invalid action" in result["error"]

    def test_execute_missing_action(self) -> None:
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True):
            result = self.command.execute({})
            assert result["success"] is False
            assert "Invalid action" in result["error"]

    def test_pyaudio_not_available(self) -> None:
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", False):
            result = self.command.execute({"action": "start"})
            assert result["success"] is False
            assert "PyAudio is not available" in result["error"]

    def test_start_recording(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()

        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream

            result = self.command.execute({"action": "start"})

            assert result["success"] is True
            assert result["status"] == "started"
            assert "sample_rate" in result
            assert "channels" in result

    def test_start_already_recording(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()

        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream

            self.command.execute({"action": "start"})
            result = self.command.execute({"action": "start"})

            assert result["success"] is True
            assert result["status"] == "already_recording"

    def test_stop_recording(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()

        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream

            self.command.execute({"action": "start"})
            result = self.command.execute({"action": "stop"})

            assert result["success"] is True
            assert result["status"] == "stopped"

    def test_stop_not_recording(self) -> None:
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True):
            result = self.command.execute({"action": "stop"})
            assert result["success"] is True
            assert result["status"] == "not_recording"

    def test_status_not_recording(self) -> None:
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True):
            result = self.command.execute({"action": "status"})

            assert result["success"] is True
            assert result["status"] == "stopped"

    def test_status_recording(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()

        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream

            self.command.execute({"action": "start"})
            result = self.command.execute({"action": "status"})

            assert result["success"] is True
            assert result["status"] == "recording"

    def test_start_with_custom_params(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()

        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream

            result = self.command.execute({
                "action": "start",
                "sample_rate": 48000,
                "channels": 2,
                "duration": 10,
            })

            assert result["success"] is True
            assert result["sample_rate"] == 48000
            assert result["channels"] == 2
            assert result["duration"] == 10

    def test_start_with_invalid_sample_rate(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()

        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream

            result = self.command.execute({"action": "start", "sample_rate": 100})
            assert result["sample_rate"] == 44100

            self.command._recording = False
            self.command._cleanup()

            result = self.command.execute({"action": "start", "sample_rate": "invalid"})
            assert result["sample_rate"] == 44100

    def test_start_with_invalid_channels(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()

        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            result = self.command.execute({"action": "start", "channels": 3})
            assert result["channels"] == 1

    def test_start_with_invalid_duration(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()

        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            result = self.command.execute({"action": "start", "duration": -5})
            assert result["duration"] is None

    def test_start_audio_initialization_failure(self) -> None:
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.side_effect = Exception("Audio init failed")

            result = self.command.execute({"action": "start"})

            assert result["success"] is False
            assert "Failed to initialize audio" in result["error"]

    def test_record_worker_captures_audio(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"audio_chunk"

        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            result = self.command.execute({"action": "start"})
            assert result["success"] is True
            time.sleep(0.2)
            self.command._stop()
            assert mock_stream.read.called

    def test_record_worker_with_duration_limit(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"audio_chunk"

        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            result = self.command.execute({"action": "start", "duration": 0.1})
            assert result["success"] is True
            time.sleep(0.15)
            assert self.command._recording is False

    def test_create_wav(self) -> None:
        self.command._sample_rate = 44100
        self.command._channels = 1
        self.command._frames = [b"chunk1", b"chunk2", b"chunk3"]

        with patch("client.commands.record_audio.wave.open") as mock_wave_open:
            mock_wav_file = MagicMock()
            mock_wave_open.return_value.__enter__ = MagicMock(return_value=mock_wav_file)
            mock_wave_open.return_value.__exit__ = MagicMock(return_value=False)
            with patch("client.commands.record_audio.base64.b64encode") as mock_b64:
                mock_b64.return_value = b"encoded_wav"
                result = self.command._create_wav()
                assert result is not None
                mock_wav_file.setnchannels.assert_called_once_with(1)
                mock_wav_file.setsampwidth.assert_called_once_with(2)
                mock_wav_file.setframerate.assert_called_once_with(44100)

    def test_create_wav_no_frames(self) -> None:
        self.command._frames = []
        result = self.command._create_wav()
        assert result is None

    def test_create_wav_exception(self) -> None:
        self.command._sample_rate = 44100
        self.command._channels = 1
        self.command._frames = [b"chunk1"]
        with patch("client.commands.record_audio.wave.open", side_effect=Exception("wav error")):
            result = self.command._create_wav()
            assert result is None

    def test_cleanup(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        self.command._audio = mock_audio
        self.command._stream = mock_stream
        self.command._frames = [b"data"]
        self.command._cleanup()
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_audio.terminate.assert_called_once()
        assert self.command._audio is None
        assert self.command._stream is None
        assert self.command._frames == []

    def test_cleanup_with_exception(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        mock_stream.stop_stream.side_effect = Exception("stop error")
        self.command._audio = mock_audio
        self.command._stream = mock_stream
        self.command._cleanup()
        assert self.command._audio is None
        assert self.command._stream is None

    def test_get_available_devices(self) -> None:
        mock_audio = MagicMock()
        mock_audio.get_device_count.return_value = 3
        mock_audio.get_device_info_by_index.side_effect = [
            {"name": "Device 1", "maxInputChannels": 2, "defaultSampleRate": 44100},
            {"name": "Device 2", "maxInputChannels": 0, "defaultSampleRate": 48000},
            {"name": "Device 3", "maxInputChannels": 1, "defaultSampleRate": 44100},
        ]
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            devices = self.command.get_available_devices()
            assert len(devices) == 2
            assert devices[0]["name"] == "Device 1"
            assert devices[1]["name"] == "Device 3"

    def test_get_available_devices_pyaudio_unavailable(self) -> None:
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", False):
            devices = self.command.get_available_devices()
            assert devices == []

    def test_get_available_devices_exception(self) -> None:
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.side_effect = Exception("device error")
            devices = self.command.get_available_devices()
            assert devices == []

    def test_record_fixed_duration(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"audio_chunk"
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            with patch.object(self.command, "_create_wav", return_value="encoded_audio"):
                result = self.command.execute({"action": "record", "duration": 0.05})
                assert result["success"] is True
                assert result["status"] in ("stopped", "not_recording")

    def test_record_fixed_duration_invalid(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            with patch.object(self.command, "_create_wav", return_value="encoded_audio"):
                result = self.command.execute({"action": "record", "duration": -1})
                assert result["success"] is True

    def test_stop_returns_audio_data(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"audio_chunk"
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            self.command.execute({"action": "start"})
            time.sleep(0.1)
            with patch.object(self.command, "_create_wav", return_value="encoded_audio"):
                result = self.command.execute({"action": "stop"})
                assert result["success"] is True
                assert "audio_data" in result
                assert result["encoding"] == "base64"
                assert result["format"] == "wav"

    def test_elapsed_time_calculation(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            self.command.execute({"action": "start"})
            time.sleep(0.1)
            result = self.command.execute({"action": "stop"})
            assert "elapsed_time" in result
            assert result["elapsed_time"] >= 0.05

    def test_status_elapsed_time(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            self.command.execute({"action": "start"})
            time.sleep(0.1)
            result = self.command.execute({"action": "status"})
            assert "elapsed_time" in result
            assert result["elapsed_time"] >= 0.05

    def test_multiple_start_stop_cycles(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            for cycle in range(3):
                start_result = self.command.execute({"action": "start"})
                assert start_result["success"] is True
                assert start_result["status"] == "started"
                status_result = self.command.execute({"action": "status"})
                assert status_result["status"] == "recording"
                stop_result = self.command.execute({"action": "stop"})
                assert stop_result["success"] is True
                assert stop_result["status"] == "stopped"

    def test_thread_safety_frame_access(self) -> None:
        import threading
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b"audio_chunk"
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            self.command.execute({"action": "start"})
            def add_frames() -> None:
                for i in range(50):
                    with self.command._frames_lock:
                         self.command._frames.append(f"frame_{threading.current_thread().name}_{i}".encode())
            threads = [threading.Thread(target=add_frames) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            frame_count = len(self.command._frames)
            self.command._stop()
            assert frame_count >= 150

    def test_error_response(self) -> None:
        result = self.command._error_response("Test error")
        assert result["success"] is False
        assert result["error"] == "Test error"

    def test_record_worker_exception_handling(self) -> None:
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.side_effect = OSError("read error")
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", True), \
             patch("client.commands.record_audio.pyaudio", create=True) as mock_pyaudio_module:
            mock_pyaudio_module.PyAudio.return_value = mock_audio
            mock_audio.open.return_value = mock_stream
            result = self.command.execute({"action": "start", "duration": 1})
            assert result["success"] is True
            time.sleep(0.2)
            assert self.command._recording is False
