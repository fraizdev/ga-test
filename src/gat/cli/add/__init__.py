import click
import structlog
from blake3 import blake3

log: structlog.BoundLogger = structlog.get_logger(__name__)


@click.command(short_help='Add path to database')
@click.argument('path')
def add(path: str) -> None:
    hasher = blake3()
    hasher.update(b'hello ')
    hasher.update(b'world')
    """Generate a hash from the provided file path."""
    log.info('Generating hash file', path=path)
