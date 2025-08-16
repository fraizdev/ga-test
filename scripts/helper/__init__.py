import subprocess
import sys
import tomllib
from collections.abc import Iterable
from datetime import datetime
from functools import cached_property
from importlib.metadata import Distribution, distribution
from pathlib import Path

import pytz
from attrs import define
from cattrs import Converter


@define
class ProjectUrls:
    Homepage: str


@define
class ProjectToml:
    name: str
    description: str
    scripts: dict[str, str]
    urls: ProjectUrls


@define
class Script:
    name: str
    path: Path
    console: bool


@define
class Project:
    @cached_property
    def _dist(self) -> Distribution:
        try:
            return distribution(self.name)
        except Exception as e:
            msg = f'Distribution for module "{self.name}" could not be found.'
            raise ModuleNotFoundError(msg) from e

    @cached_property
    def _toml(self) -> ProjectToml:
        with (self.root / 'pyproject.toml').open('rb') as file:
            data = tomllib.load(file)
        return Converter().structure(data.get('project', {}), ProjectToml)

    def _get_module(self, script_entry: str) -> Path:
        module_part, func_part = script_entry.split(':', maxsplit=1)
        module_parent = self.root / 'src' / Path(*module_part.split('.'))
        for possible_module in (func_part, '__main__', '__init__'):
            if (module_file := (module_parent / f'{possible_module}.py')).is_file():
                return module_file

        msg = f'File for module "{script_entry}" could not be found.'
        raise ModuleNotFoundError(msg)

    @cached_property
    def root(self) -> Path:
        return Path.cwd()

    @property
    def name(self) -> str:
        return self._toml.name

    @property
    def homepage(self) -> str:
        return self._toml.urls.Homepage

    @property
    def scripts(self) -> Iterable[Script]:
        for name, script_entry in self._toml.scripts.items():
            module_path = self._get_module(script_entry)
            is_console = 'cli' in str(module_path)
            yield Script(name, module_path, is_console)

    @property
    def version(self) -> str:
        return self._dist.version

    @property
    def version_tuple(self) -> tuple[int, int, int, int]:
        parts = self.version.split('.', maxsplit=3)
        numbers = []

        for part in parts:
            if not part.isdigit():
                break
            numbers.append(int(part))

        padded = numbers + [0] * (4 - len(numbers))
        return padded[0], padded[1], padded[2], padded[3]

    @property
    def description(self) -> str:
        return self._toml.description

    @property
    def company_name(self) -> str:
        return f'The {self.description} Authors'

    @cached_property
    def copyright(self) -> str:
        current_year = datetime.now(pytz.UTC).year
        return f'Copyright (C) {current_year} {self.company_name}'


def run_command(command: list[str]) -> None:
    process = subprocess.run(command, check=False)
    if process.returncode:
        sys.exit(process.returncode)
