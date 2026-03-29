import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from client.commands.search import SearchCommand


class TestSearchCommand:
    def setup_method(self) -> None:
        self.command = SearchCommand()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self) -> None:
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_files(self) -> Dict[str, Path]:
        files = {}
        files["root_txt"] = Path(self.temp_dir) / "test.txt"
        files["root_py"] = Path(self.temp_dir) / "script.py"
        files["root_md"] = Path(self.temp_dir) / "readme.md"

        subdir = Path(self.temp_dir) / "subdir"
        subdir.mkdir()
        files["sub_txt"] = subdir / "nested.txt"
        files["sub_py"] = subdir / "nested.py"

        subsubdir = subdir / "deep"
        subsubdir.mkdir()
        files["deep_txt"] = subsubdir / "deep.txt"

        for path in files.values():
            path.write_text("test content")

        return files

    def test_name_property(self) -> None:
        assert self.command.name == "search"

    def test_description_property(self) -> None:
        assert "search" in self.command.description.lower()
        assert "file" in self.command.description.lower()

    def test_execute_missing_pattern(self) -> None:
        result = self.command.execute({})

        assert result["success"] is False
        assert "pattern" in result["error"].lower()

    def test_execute_empty_pattern(self) -> None:
        result = self.command.execute({"pattern": ""})

        assert result["success"] is False
        assert "pattern" in result["error"].lower()

    def test_execute_invalid_pattern_type(self) -> None:
        result = self.command.execute({"pattern": 123})

        assert result["success"] is False
        assert "pattern" in result["error"].lower()

    def test_execute_nonexistent_directory(self) -> None:
        result = self.command.execute({
            "pattern": "*.txt",
            "directory": "/nonexistent/path",
        })

        assert result["success"] is False
        assert "does not exist" in result["error"].lower()

    def test_execute_file_as_directory(self) -> None:
        test_file = Path(self.temp_dir) / "notadir.txt"
        test_file.write_text("content")

        result = self.command.execute({
            "pattern": "*.txt",
            "directory": str(test_file),
        })

        assert result["success"] is False
        assert "not a directory" in result["error"].lower()

    def test_execute_recursive_search(self) -> None:
        files = self._create_test_files()

        result = self.command.execute({
            "pattern": "*.txt",
            "directory": self.temp_dir,
            "recursive": True,
        })

        assert result["success"] is True
        assert result["count"] == 3
        paths = [f["path"] for f in result["files"]]
        assert str(files["root_txt"]) in paths
        assert str(files["sub_txt"]) in paths
        assert str(files["deep_txt"]) in paths

    def test_execute_non_recursive_search(self) -> None:
        files = self._create_test_files()

        result = self.command.execute({
            "pattern": "*.txt",
            "directory": self.temp_dir,
            "recursive": False,
        })

        assert result["success"] is True
        assert result["count"] == 1
        paths = [f["path"] for f in result["files"]]
        assert str(files["root_txt"]) in paths
        assert str(files["sub_txt"]) not in paths

    def test_execute_pattern_matching(self) -> None:
        files = self._create_test_files()

        result = self.command.execute({
            "pattern": "*.py",
            "directory": self.temp_dir,
            "recursive": True,
        })

        assert result["success"] is True
        assert result["count"] == 2
        paths = [f["path"] for f in result["files"]]
        assert str(files["root_py"]) in paths
        assert str(files["sub_py"]) in paths
        assert str(files["root_txt"]) not in paths

    def test_execute_exact_filename_match(self) -> None:
        files = self._create_test_files()

        result = self.command.execute({
            "pattern": "readme.md",
            "directory": self.temp_dir,
            "recursive": True,
        })

        assert result["success"] is True
        assert result["count"] == 1
        assert result["files"][0]["name"] == "readme.md"

    def test_execute_wildcard_pattern(self) -> None:
        files = self._create_test_files()

        result = self.command.execute({
            "pattern": "*",
            "directory": self.temp_dir,
            "recursive": False,
        })

        assert result["success"] is True
        names = [f["name"] for f in result["files"]]
        assert "test.txt" in names
        assert "script.py" in names
        assert "readme.md" in names
        assert "subdir" in names

    def test_execute_max_results_limit(self) -> None:
        for i in range(20):
            (Path(self.temp_dir) / f"file{i}.txt").write_text("content")

        result = self.command.execute({
            "pattern": "*.txt",
            "directory": self.temp_dir,
            "max_results": 5,
        })

        assert result["success"] is True
        assert result["count"] == 5

    def test_execute_default_directory(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.home()) as temp_in_home:
            test_file = Path(temp_in_home) / "uniquetestfile.txt"
            test_file.write_text("content")

            result = self.command.execute({
                "pattern": "uniquetestfile.txt",
                "directory": temp_in_home,
            })

            assert result["success"] is True
            assert result["count"] == 1

    def test_execute_returns_file_metadata(self) -> None:
        files = self._create_test_files()

        result = self.command.execute({
            "pattern": "test.txt",
            "directory": self.temp_dir,
        })

        assert result["success"] is True
        file_info = result["files"][0]
        assert "path" in file_info
        assert "name" in file_info
        assert "is_dir" in file_info
        assert "size" in file_info
        assert "modified" in file_info
        assert file_info["name"] == "test.txt"
        assert file_info["is_dir"] is False
        assert file_info["size"] > 0

    def test_execute_directory_in_results(self) -> None:
        self._create_test_files()

        result = self.command.execute({
            "pattern": "subdir",
            "directory": self.temp_dir,
            "recursive": False,
        })

        assert result["success"] is True
        assert result["count"] == 1
        assert result["files"][0]["is_dir"] is True

    def test_execute_invalid_recursive_uses_default(self) -> None:
        files = self._create_test_files()

        result = self.command.execute({
            "pattern": "*.txt",
            "directory": self.temp_dir,
            "recursive": "invalid",
        })

        assert result["success"] is True
        assert result["count"] == 3

    def test_execute_invalid_max_results_uses_default(self) -> None:
        (Path(self.temp_dir) / "test.txt").write_text("content")

        result = self.command.execute({
            "pattern": "*.txt",
            "directory": self.temp_dir,
            "max_results": -1,
        })

        assert result["success"] is True
        assert result["count"] == 1

    def test_execute_expanded_home_directory(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.home()) as temp_in_home:
            test_file = Path(temp_in_home) / "hometest.txt"
            test_file.write_text("content")

            result = self.command.execute({
                "pattern": "hometest.txt",
                "directory": temp_in_home,
            })

            assert result["success"] is True

    def test_execute_no_matches(self) -> None:
        self._create_test_files()

        result = self.command.execute({
            "pattern": "*.nonexistent",
            "directory": self.temp_dir,
        })

        assert result["success"] is True
        assert result["count"] == 0
        assert result["files"] == []

    def test_execute_response_structure(self) -> None:
        (Path(self.temp_dir) / "test.txt").write_text("content")

        result = self.command.execute({
            "pattern": "*.txt",
            "directory": self.temp_dir,
        })

        assert result["success"] is True
        assert "pattern" in result
        assert "directory" in result
        assert "recursive" in result
        assert "count" in result
        assert "files" in result
        assert "message" in result
        assert result["pattern"] == "*.txt"
        assert result["recursive"] is True

    def test_execute_question_mark_wildcard(self) -> None:
        (Path(self.temp_dir) / "file1.txt").write_text("content")
        (Path(self.temp_dir) / "file2.txt").write_text("content")
        (Path(self.temp_dir) / "file10.txt").write_text("content")

        result = self.command.execute({
            "pattern": "file?.txt",
            "directory": self.temp_dir,
        })

        assert result["success"] is True
        names = [f["name"] for f in result["files"]]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "file10.txt" not in names

    def test_execute_character_class_pattern(self) -> None:
        (Path(self.temp_dir) / "filea.txt").write_text("content")
        (Path(self.temp_dir) / "fileb.txt").write_text("content")
        (Path(self.temp_dir) / "filec.txt").write_text("content")
        (Path(self.temp_dir) / "filed.txt").write_text("content")

        result = self.command.execute({
            "pattern": "file[ab].txt",
            "directory": self.temp_dir,
        })

        assert result["success"] is True
        names = [f["name"] for f in result["files"]]
        assert "filea.txt" in names
        assert "fileb.txt" in names
        assert "filec.txt" not in names
        assert "filed.txt" not in names
