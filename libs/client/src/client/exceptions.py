from attrs import define, field


@define
class SocketPathError(Exception):
    message: str = field(
        default=(
            'Failed to determine socket base directory. '
            'Please set one of: XDG_RUNTIME_DIR, HOME, or TMPDIR.'
        ),
        init=False,
    )

    def __str__(self) -> str:
        return self.message


@define
class SocketValidateError(Exception):
    path: str
    message: str = field(
        default=('Failed to determine socket path "{path}".'),
        init=False,
    )

    def __str__(self) -> str:
        return self.message.format(path=self.path)
