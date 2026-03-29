import fnmatch
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)


class SearchCommand(BaseCommand):

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search for files"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pattern = params.get("pattern")
        if not pattern or not isinstance(pattern, str):
            return self._error_response("Missing or invalid 'pattern' parameter")

        directory = params.get("directory")
        if not directory or not isinstance(directory, str):
            directory = str(Path.home())

        recursive = params.get("recursive", True)
        if not isinstance(recursive, bool):
            recursive = True

        max_results = params.get("max_results", 1000)
        if not isinstance(max_results, int) or max_results < 1:
            max_results = 1000

        try:
            directory_path = Path(directory).expanduser().resolve()

            if not directory_path.exists():
                return self._error_response(f"Directory does not exist: {directory}")

            if not directory_path.is_dir():
                return self._error_response(f"Path is not a directory: {directory}")

            matches = self._search_files(
                directory_path, pattern, recursive, max_results
            )

            logger.info(
                f"Search completed: pattern='{pattern}', directory='{directory}', "
                f"recursive={recursive}, found={len(matches)} files"
            )

            return {
                "success": True,
                "pattern": pattern,
                "directory": str(directory_path),
                "recursive": recursive,
                "count": len(matches),
                "files": matches,
                "message": f"Found {len(matches)} file(s) matching '{pattern}'",
            }

        except PermissionError as e:
            logger.error(f"Permission denied during search: {e}")
            return self._error_response(f"Permission denied: {e}")
        except Exception as e:
            logger.error(f"Search error: {e}")
            return self._error_response(f"Search failed: {e}")

    def _search_files(
        self, directory: Path, pattern: str, recursive: bool, max_results: int
    ) -> List[Dict[str, Any]]:
        matches = []

        if recursive:
            walker = directory.rglob("*")
        else:
            walker = directory.glob("*")

        for path in walker:
            if len(matches) >= max_results:
                logger.warning(f"Max results ({max_results}) reached, truncating")
                break

            if fnmatch.fnmatch(path.name, pattern):
                try:
                    stat = path.stat()
                    matches.append({
                        "path": str(path),
                        "name": path.name,
                        "is_dir": path.is_dir(),
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    })
                except (PermissionError, OSError) as e:
                    logger.debug(f"Cannot access {path}: {e}")
                    matches.append({
                        "path": str(path),
                        "name": path.name,
                        "is_dir": path.is_dir(),
                        "size": None,
                        "modified": None,
                        "error": str(e),
                    })

        return matches

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": message,
        }
