import argparse
import logging
import sys
from typing import Optional

from common.constants import DEFAULT_HOST, DEFAULT_PORT
from server.core import Server
from server.output import OutputFormatter

# Global reference to current server instance for prompt restoration
_current_server: Optional[Server] = None


class PromptRestoringHandler(logging.Handler):
    # Custom handler that restores the prompt after emitting log records.

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                print(f"\r{msg}", file=sys.stderr)
            else:
                print(f"\r{msg}")
            if _current_server is not None and _current_server.running:
                prompt = _current_server._get_prompt()
                print(prompt, end="", flush=True)
        except Exception:
            self.handleError(record)


def parse_args() -> argparse.Namespace:
    # Parse command-line arguments.
    parser = argparse.ArgumentParser(
        description="BiggusRatus Server - Remote Administration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m server.server                    # Start server on default port 4444
  python -m server.server --port 8443        # Start server on port 8443
  python -m server.server --host 0.0.0.0     # Listen on all interfaces
  python -m server.server --verbose          # Enable debug logging
        """,
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help=f"Host address to bind to (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging",
    )
    return parser.parse_args()


def main() -> None:
    global _current_server
    args = parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO

    # Configure logging with prompt-restoring handler
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = PromptRestoringHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    root_logger.addHandler(handler)

    server = Server(host=args.host, port=args.port)
    _current_server = server
    try:
        server.start()
        server.run_interactive()
    except KeyboardInterrupt:
        OutputFormatter.info("Interrupt received")
    finally:
        _current_server = None
        server.stop()


if __name__ == "__main__":
    main()
