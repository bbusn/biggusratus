import argparse
import logging
import os
import select
import signal
import sys
from typing import Optional

from common.constants import DEFAULT_HOST, DEFAULT_PORT
from server.core import Server, _prompt_lock
from server.output import OutputFormatter
from server.web import start_web_server

# Global reference to current server instance for prompt restoration
_current_server: Optional[Server] = None
_wakeup_read: Optional[int] = None
_wakeup_write: Optional[int] = None


class PromptRestoringHandler(logging.Handler):
    # Custom handler that restores the prompt after emitting log records.

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            with _prompt_lock:
                # Clear the current line and print the message
                if record.levelno >= logging.ERROR:
                    print(f"\r\033[K{msg}", file=sys.stderr, flush=True)
                else:
                    print(f"\r\033[K{msg}", flush=True)
                if _current_server is not None and _current_server.running:
                    prompt = _current_server._get_prompt()
                    print(prompt, end="", flush=True)
        except Exception:
            self.handleError(record)


def _signal_handler(signum, frame):
    if _current_server is not None:
        _current_server.running = False
    # Write to wakeup pipe to interrupt select
    if _wakeup_write is not None:
        try:
            os.write(_wakeup_write, b'\x00')
        except OSError:
            pass


def parse_args() -> argparse.Namespace:
    # Parse command-line arguments.
    parser = argparse.ArgumentParser(
        description="BiggusRatus Server - Remote Administration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m server.server                    # Start server on default port 8443
  python -m server.server --port 9443        # Start server on port 9443
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
    parser.add_argument(
        "--web-port",
        type=int,
        default=8080,
        help="Port for web interface (default: 8080)",
    )
    return parser.parse_args()


def main() -> None:
    global _current_server, _wakeup_read, _wakeup_write
    args = parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO

    # Create wakeup pipe for signal handling
    _wakeup_read, _wakeup_write = os.pipe()
    os.set_blocking(_wakeup_read, False)
    os.set_blocking(_wakeup_write, False)

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
    
    web_httpd = start_web_server(args.host, args.web_port, server)
    
    signal.signal(signal.SIGINT, _signal_handler)
    
    try:
        server.start()
        server.run_interactive(_wakeup_read)
        OutputFormatter.info("Interrupt received")
    finally:
        _current_server = None
        server.stop()
        web_httpd.shutdown()
        # Remove handler before shutdown to avoid lock issues
        root_logger.removeHandler(handler)
        handler.close()
        # Close wakeup pipe
        if _wakeup_read is not None:
            os.close(_wakeup_read)
        if _wakeup_write is not None:
            os.close(_wakeup_write)


if __name__ == "__main__":
    main()
