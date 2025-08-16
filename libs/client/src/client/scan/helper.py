import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path

import structlog

from client.scan.exceptions import DirectoryError

log: structlog.BoundLogger = structlog.get_logger(__name__)


def validate_directory(base_directory: str | Path) -> Path:
    path = Path(base_directory).resolve()
    if not path.is_dir():
        raise DirectoryError(path)
    return path


def matches_pattern(name: str, pattern: str | None) -> bool:
    return pattern is None or fnmatch.fnmatch(name, pattern)


def safe_scandir(path: Path) -> Iterator[os.DirEntry[str]]:
    try:
        with os.scandir(path) as entries:
            yield from entries
    except PermissionError:
        log.warning('Access denied: Cannot open directory', directory=path)
    except FileNotFoundError:
        log.warning('The directory no longer exists.', directory=path)
    except Exception:
        log.exception('An unexpected error occurred while listing the contents', directory=path)


def should_skip_symlink(dir_entry: os.DirEntry[str], dir_path: Path) -> bool:
    if not dir_entry.is_symlink():
        return False

    try:
        real_target = dir_path.resolve()

    except FileNotFoundError:
        log.warning('The symlink points to a non-existent target', symlink=dir_path)
        return True
    except RecursionError:
        log.warning('Circular symlink detected', symlink=dir_path)
        return True
    except (PermissionError, OSError):
        log.warning('Could not resolve symlink', symlink=dir_path)
        return True

    return real_target == dir_path or real_target in dir_path.parents
