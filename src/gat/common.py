from client.config import user_config_dir
from client.log import configure_logging

from fhash._version import __version__

PROG_NAME = 'fhash'
IS_DEV = 'dev' in __version__


def config_log(filename: str) -> None:
    logfile = user_config_dir(PROG_NAME) / f'{filename}.log'
    configure_logging(logfile, is_dev=IS_DEV)
