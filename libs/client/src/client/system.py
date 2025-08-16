import platform
from functools import cache
from typing import TYPE_CHECKING

from attrs import define

if TYPE_CHECKING:
    from collections.abc import Sequence


@cache
def windows_check() -> bool:
    return platform.system() in {'Windows', 'Microsoft'}


@cache
def vista_check() -> bool:
    return windows_check() and platform.release() == 'Vista'


@cache
def osx_check() -> bool:
    return platform.system() == 'Darwin'


@cache
def linux_check() -> bool:
    return platform.system() == 'Linux'


@cache
def is_wsl() -> bool:
    return linux_check() and 'microsoft' in platform.uname().release.lower()


@cache
def get_os_version() -> str:
    os_version: Sequence[str]
    if windows_check():
        os_version = platform.win32_ver()
    elif osx_check():
        release, _, machine = platform.mac_ver()
        os_version = [release, '', machine]
    else:
        try:
            import distro

            os_version = (distro.name(), distro.version(), distro.codename())
        except ImportError:
            os_version = (platform.release(),)

    return ' '.join(filter(None, os_version))


@define
class VersionDetail:
    python: str
    os: str


@cache
def get_version_detail() -> VersionDetail:
    return VersionDetail(
        python=platform.python_version(), os=f'{platform.system()} {get_os_version()}'
    )
