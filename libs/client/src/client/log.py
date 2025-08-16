import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from client.constant import DEFAULT_BACKUP_COUNT, DEFAULT_LOG_FILE_SIZE

if TYPE_CHECKING:
    from structlog.typing import Processor


def configure_logging(logfile: Path, *, is_dev: bool = True) -> None:
    timestamper = structlog.processors.TimeStamper(fmt='%Y-%m-%d %H:%M:%S')
    shared_processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.UnicodeDecoder(),
        timestamper,
    ]

    processors = [
        *shared_processors,
        structlog.stdlib.filter_by_level,
    ]

    if is_dev:
        processors.extend([
            structlog.stdlib.add_logger_name,
            structlog.processors.CallsiteParameterAdder(
                parameters=[structlog.processors.CallsiteParameter.LINENO]
            ),
        ])

    structlog.configure(
        processors=[
            *processors,
            structlog.processors.StackInfoRenderer(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log_level = logging.DEBUG if is_dev else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    existing_handler_types = {type(h) for h in root_logger.handlers}

    if RotatingFileHandler not in existing_handler_types:
        file_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(),
            ],
        )
        file_handler = RotatingFileHandler(
            logfile, maxBytes=DEFAULT_LOG_FILE_SIZE, backupCount=DEFAULT_BACKUP_COUNT
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    if is_dev and logging.StreamHandler not in existing_handler_types:
        console_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(),
            ],
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
