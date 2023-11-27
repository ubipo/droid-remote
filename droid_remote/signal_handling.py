import logging
import signal
import asyncio
from asyncio.tasks import Task


logger = logging.getLogger(__name__)


async def stop_server(tasks_to_cancel: list[Task]):
    for task in tasks_to_cancel:
        task.cancel()
    logger.info("All tasks cancelled. Waiting for them to finish...")
    await asyncio.gather(*tasks_to_cancel, return_exceptions=True)


def add_signal_handlers(tasks_to_cancel: list[Task]):
    is_stopping = False

    def stop_for_signal(sig: signal.Signals):
        nonlocal is_stopping
        if is_stopping:
            return
        logger.info(f"Received signal {sig.name}. Stopping server...")
        is_stopping = True
        asyncio.create_task(stop_server(tasks_to_cancel))

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop = asyncio.get_running_loop()

        def handler():
            return stop_for_signal(sig)

        loop.add_signal_handler(sig, handler)
