import logging
from logging.handlers import TimedRotatingFileHandler
import sys
from pathlib import Path
from typing import Optional
from .event_bus import EventBus, EventBusLogHandler


def setup_logging(log_file_path: Path, event_bus: Optional[EventBus] = None):
    handlers: list[logging.Handler] = [
        TimedRotatingFileHandler(
            log_file_path,
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ]
    if event_bus is not None:
        handlers.append(EventBusLogHandler(event_bus))
    logging.basicConfig(level=logging.DEBUG, handlers=handlers, force=True)
    logging.getLogger("aiohttp.access").disabled = True
    logging.getLogger("asyncio").disabled = True
