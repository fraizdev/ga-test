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


def walk_files(dir_entry: os.DirEntry[str], pattern: str | None) -> Iterator[Path]:
    entry_path = Path(dir_entry.path)

    if dir_entry.is_file():
        if matches_pattern(dir_entry.name, pattern):
            yield entry_path

    elif dir_entry.is_dir():
        if should_skip_symlink(dir_entry, entry_path):
            return

        for child_entry in safe_scandir(entry_path):
            yield from walk_files(child_entry, pattern)


def rscan_files(base_directory: str | Path, pattern: str | None = None) -> Iterator[Path]:
    root = validate_directory(base_directory)
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(walk_files, file_entry, pattern) for file_entry in safe_scandir(root)
        ]
        for future in as_completed(futures):
            yield from future.result()


def scan_files(base_directory: str | Path, pattern: str | None = None) -> Iterator[Path]:
    root = validate_directory(base_directory)
    for file_entry in root.iterdir():
        if file_entry.is_file() and matches_pattern(file_entry.name, pattern):
            yield file_entry
