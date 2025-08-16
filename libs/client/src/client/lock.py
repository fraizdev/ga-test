import hashlib
import os
import sys
import tempfile
import time
from contextlib import suppress
from errno import EACCES, ENOSYS
from functools import cached_property
from pathlib import Path
from typing import Self, cast

import structlog
from attrs import define, field

from client.system import windows_check

log: structlog.BoundLogger = structlog.get_logger(__name__)


@define
class AcquireLock:
    lock: 'LockClient'

    def __enter__(self) -> 'LockClient':
        return self.lock

    def __exit__(self, *_: object) -> None:
        self.lock.release()


@define
class LockClient:
    _mode: int = field(default=0o644, init=False, repr=False)
    _fd: int | None = field(default=None, init=False, repr=False)

    @cached_property
    def lockfile(self) -> Path:
        filename = Path(sys.argv[0]).resolve()
        filehash = hashlib.blake2b(str(filename).encode('utf-8'))
        return Path(tempfile.gettempdir(), f'{filehash.hexdigest()}.lock')

    def acquire(self) -> AcquireLock:
        if not self.is_locked:
            log.debug(
                'Acquiring lock on file',
                lockfile=self.lockfile,
                platform='Windows' if windows_check() else 'Unix',
            )
            flags: int = os.O_RDWR | os.O_CREAT | os.O_EXCL
            try:
                self._fd = os.open(self.lockfile, flags, self._mode)

            except OSError as err:
                if err.errno == EACCES:
                    log.warning('Permission denied when opening lockfile', lockfile=self.lockfile)
                else:
                    log.exception(
                        'Failed to open lockfile',
                        lockfile=self.lockfile,
                        reason='Unexcpected error',
                    )

                self._fd = None
            else:
                fd = self._fd
                try:
                    if windows_check():
                        import msvcrt

                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]
                except OSError as err:
                    if err.errno != EACCES:
                        log.warning(
                            'Permission denied during file lock operation', lockfile=self.lockfile
                        )
                    elif err.errno == ENOSYS:
                        log.exception(
                            'Locking not supported on filesystem',
                            module='msvcrt' if windows_check() else 'fcntl',
                        )
                    else:
                        log.exception(
                            'Failed to locking file',
                            lockfile=self.lockfile,
                            reason='Unexpected error',
                        )

                    os.close(fd)
                    self._fd = None

        return AcquireLock(lock=self)

    def release(self) -> None:
        if not self.is_locked:
            return

        time.sleep(0.3)

        log.debug('Release lock', lockfile=self.lockfile)
        fd = cast('int', self._fd)
        try:
            if windows_check():
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                with suppress(PermissionError):
                    os.fchmod(fd, self._mode)
                fcntl.flock(fd, fcntl.LOCK_UN)  # type: ignore[attr-defined]

            os.close(fd)
        except Exception:
            log.exception('Lock release failed', lockfile=self.lockfile)
        else:
            log.debug('Lock release successfully', lockfile=self.lockfile)
            self._fd = None

        with suppress(FileNotFoundError):
            self.lockfile.unlink(missing_ok=True)

    @property
    def is_locked(self) -> bool:
        return self._fd is not None

    @property
    def exists_running(self) -> bool:
        if self.is_locked or not self.lockfile.exists():
            return False

        try:
            with self.lockfile.open('r+') as file:
                if windows_check():
                    import msvcrt

                    msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
                    msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(file.fileno(), fcntl.LOCK_NB)  # type: ignore[attr-defined]
                    fcntl.flock(file.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]

        except OSError:
            return True

        return False

    def wait(self, timeout: float | None = None, interval: float = 1.0) -> bool:
        start = time.monotonic()

        log.debug('Wait for other lock to end', interval=interval)

        while self.exists_running:
            if timeout is not None and (time.monotonic() - start) >= timeout:
                return False

            time.sleep(interval)

        return True

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
