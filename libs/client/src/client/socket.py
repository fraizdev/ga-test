import os
import socket
from functools import cached_property
from pathlib import Path
from typing import BinaryIO, Self, cast

import structlog
from attrs import define, field

from client.constant import MAX_PREVIEW_LENGTH
from client.exceptions import SocketPathError, SocketValidateError
from client.system import windows_check

log: structlog.BoundLogger = structlog.get_logger(__name__)


@define
class ConnectSocket:
    socket: 'SocketClient'

    def __enter__(self) -> 'SocketClient':
        return self.socket

    def __exit__(self, *_: object) -> None:
        self.socket.disconnect()


def validate_default_path(_: object, __: object, value: str | None) -> None:
    if value is None:
        return

    if not value.strip():
        raise SocketValidateError(path=value)

    if windows_check():
        normalized = value.rstrip('\\').lower()
        if normalized != value or not normalized.startswith(r'\\.\pipe'):
            raise SocketValidateError(path=value)
    elif Path(value).is_dir():
        raise SocketValidateError(path=value)


@define
class SocketClient:
    name: str
    default_path: str | None = field(default=None, validator=validate_default_path)
    _pipe: socket.socket | BinaryIO | None = field(default=None, init=False, repr=False)

    @cached_property
    def socket_path(self) -> str:
        if self.default_path:
            return self.default_path

        if windows_check():
            return rf'\\.\pipe\{self.name}'

        for var in ('XDG_RUNTIME_DIR', 'HOME', 'TMPDIR'):
            base_dir = os.getenv(var)
            if base_dir:
                return str(Path(base_dir) / f'.{self.name}')

        raise SocketPathError

    def connect(self) -> ConnectSocket:
        if not self.is_connect:
            log.debug(
                'Attempting to connecting socket',
                socket=self.socket_path,
                platform='Windows' if windows_check() else 'Unix',
            )

            try:
                if windows_check():
                    self._pipe = open(self.socket_path, 'r+b', buffering=0)  # noqa: SIM115, PTH123
                else:
                    sock = socket.socket(socket.AF_UNIX)  # type: ignore[attr-defined]
                    sock.connect(self.socket_path)
                    self._pipe = sock
            except (FileNotFoundError, ConnectionRefusedError):
                log.exception(
                    'Socket connection failed',
                    socket_path=self.socket_path,
                    reason='File not found or connection refused',
                )
                self._pipe = None
            else:
                log.debug(
                    'Socket connection established',
                    socket_path=self.socket_path,
                    connection_type='pipe' if windows_check() else 'unix',
                )

        return ConnectSocket(socket=self)

    def disconnect(self) -> None:
        if not self.is_connect:
            return

        log.debug('Disconnecting socket', socket_path=self.socket_path)
        pipe = cast('socket.socket | BinaryIO', self._pipe)
        try:
            pipe.close()
        except Exception:
            log.exception('Socket close failed', socket_path=self.socket_path)
        else:
            log.debug('Socket disconnected successfully', socket_path=self.socket_path)
            self._pipe = None

    def send(self, line: str) -> None:
        if not self.is_connect:
            return

        try:
            data = line.encode('utf-8')
            log.debug(
                'Sending data over socket',
                socket_path=self.socket_path,
                bytes=len(data),
                content_preview=(
                    line[:MAX_PREVIEW_LENGTH] + ('...' if len(line) > MAX_PREVIEW_LENGTH else '')
                ),
            )
            pipe = cast('socket.socket | BinaryIO', self._pipe)
            send = pipe.send if isinstance(pipe, socket.socket) else pipe.write
            send(data)
        except Exception:
            log.exception('Failed to send data over socket', socket_path=self.socket_path)
        else:
            log.debug(
                'Data sent successfully', socket_path=self.socket_path, content_length=len(line)
            )

    @property
    def is_connect(self) -> bool:
        return self._pipe is not None

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()
