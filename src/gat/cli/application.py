from attrs import define, field
from rich.console import Console


@define
class Application:
    _console: Console = field(factory=Console, init=False)

    def echo(self, *args: str) -> None:
        self._console.print(*args)
