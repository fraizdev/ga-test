from pathlib import Path

from attrs import define, field


@define
class DirectoryError(Exception):
    path: Path
    message: str = field(
        default='The path "{path}" is either invalid or not a directory.', init=False
    )

    def __str__(self) -> str:
        return self.message.format(path=self.path)
