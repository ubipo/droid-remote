import asyncio
import logging
from asyncio import Future
from typing import Any


class EventBus:
    """Async event bus

    Usage:
    ```
    event_bus = EventBus()
    async for event in event_bus:
      print(event)
    ```
    """

    def __init__(self) -> None:
        self._iter_futures: set[Future] = set()

    def emit(self, event: Any):
        for future in self._iter_futures:
            try:
                future.set_result(event)
            except asyncio.InvalidStateError:
                pass
        self._iter_futures.clear()

    def __aiter__(self):
        return self

    async def __anext__(self):
        future = Future()
        self._iter_futures.add(future)
        return await future


class EventBusLogHandler(logging.Handler):
    event_bus: EventBus

    def __init__(self, event_bus: EventBus) -> None:
        super().__init__()
        self.event_bus = event_bus

    def emit(self, record):
        self.event_bus.emit(self.format(record))
