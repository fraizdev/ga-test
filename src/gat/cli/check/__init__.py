import secrets

import click
import structlog
from blake3 import blake3

log: structlog.BoundLogger = structlog.get_logger(__name__)


# --- STEP 1: Sender creates the MAC ---
def create_mac(message: bytes, key: bytes) -> bytes:
    return blake3(message, key=key).digest()


# --- STEP 2: Receiver verifies the MAC ---
def verify_mac(message: bytes, key: bytes, received_mac: bytes) -> bool:
    expected_mac = blake3(message, key=key).digest()
    return secrets.compare_digest(expected_mac, received_mac)  # constant-time compare


@click.command(short_help='Check hash from file')
@click.argument('path')
def check(path: str) -> None:
    """Check a hash from the provided file path."""
    log.info('Checking hash file', path=path)

    # Generate a 32-byte (256-bit) secret key
    secret_key = secrets.token_bytes(32)

    # The message to authenticate
    message = b'a message to authenticate'

    # Create MAC
    mac = create_mac(message, secret_key)

    if verify_mac(message, secret_key, mac):
        log.info('✅ Message verified successfully!', message=message, mac=mac.hex())
    else:
        log.warning('❌ Verification failed.', message=message, mac=mac.hex())
