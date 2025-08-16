import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from client.scan.helper import (
    matches_pattern,
    safe_scandir,
    should_skip_symlink,
    validate_directory,
)


def walk_directories(dir_entry: os.DirEntry[str], pattern: str | None) -> Iterator[Path]:
    entry_path = Path(dir_entry.path)

    if dir_entry.is_dir():
        if should_skip_symlink(dir_entry, entry_path):
            return

        if matches_pattern(dir_entry.name, pattern):
            yield entry_path

        for child_entry in safe_scandir(entry_path):
            yield from walk_directories(child_entry, pattern)


def rscan_directories(base_directory: str | Path, pattern: str | None = None) -> Iterator[Path]:
    root = validate_directory(base_directory)
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(walk_directories, dir_entry, pattern)
            for dir_entry in safe_scandir(root)
        ]
        for future in as_completed(futures):
            yield from future.result()


def scan_directories(base_directory: str | Path, pattern: str | None = None) -> Iterator[Path]:
    root = validate_directory(base_directory)
    for dir_entry in root.iterdir():
        if dir_entry.is_dir() and matches_pattern(dir_entry.name, pattern):
            yield dir_entry
