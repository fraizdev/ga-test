import click
import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)


@click.command(short_help='Generate hash from file')
@click.argument('path')
def generate(path: str) -> None:
    """Generate a hash from the provided file path."""
    log.info('Generating hash file', path=path)
