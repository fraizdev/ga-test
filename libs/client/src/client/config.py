import os
from pathlib import Path

import structlog

from client.system import windows_check

log: structlog.BoundLogger = structlog.get_logger(__name__)


def _get_windows_appdata_path() -> Path | None:
    app_data = os.getenv('APPDATA')
    if app_data:
        return Path(app_data)

    reg_path = r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as hkey:
            app_data, _ = winreg.QueryValueEx(hkey, 'AppData')
            return Path(app_data)

    except (FileNotFoundError, PermissionError, OSError):
        log.exception(
            'Error accessing "AppData" from registry key', reg_path=f'HKEY_CURRENT_USER\\{reg_path}'
        )

    return None


def user_config_dir(*resources: str | Path) -> Path:
    base_config_dir = _get_windows_appdata_path() if windows_check() else None

    if base_config_dir is None:
        base_config_dir = Path(os.getenv('XDG_CONFIG_HOME', Path.home() / '.config'))

    full_path = base_config_dir / Path(*resources)
    full_path.mkdir(parents=True, mode=0o700, exist_ok=True)

    return full_path
