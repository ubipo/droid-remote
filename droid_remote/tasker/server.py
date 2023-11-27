import asyncio
import logging
from typing import Callable
from aiohttp import web as aio_web
from .exceptions import UnknownTaskException, TaskExecutionException
from .model import CallbackFutures, TaskCallbackData


HTTP_PORT = 2981  # https://xkcd.com/221/
logger = logging.getLogger(__name__)


def create_aio_task_callback_handler(
    handle_task_callback: Callable[[TaskCallbackData], None],
):
    async def handler(request: aio_web.Request):
        body = await request.text()
        try:
            callback_data = TaskCallbackData.from_json(body)
        except Exception as e:
            logger.exception("Failed to parse task callback data")
            return aio_web.Response(text=f"Failed to parse task callback data: {e}")
        handle_task_callback(callback_data)
        return aio_web.Response(text="OK")

    return handler


def create_futures_task_callback_handler(
    callback_futures: CallbackFutures,
):
    def handler(callback_data: TaskCallbackData):
        logger.debug(f"Received task callback: {callback_data}")
        correlation_id = callback_data.correlation_id
        msg_prefix = f"Callback for Tasker task with {correlation_id=}:"
        try:
            callback_future = callback_futures[correlation_id]
        except KeyError:
            logger.warn(f"{msg_prefix} no callback future found")
            return
        return_code = callback_data.return_code
        result = callback_data.result
        msg_prefix = f"Tasker task with {correlation_id=}:"
        if return_code == 1:
            task_name = result
            logger.warn(f"{msg_prefix} unknown task name '{task_name}'")
            callback_future.set_exception(UnknownTaskException(task_name))
        elif return_code != 0:
            logger.warn(f"{msg_prefix} returned non-zero return code: {return_code}")
            callback_future.set_exception(TaskExecutionException(return_code, result))
        else:
            callback_future.set_result(result)
        try:
            del callback_futures[correlation_id]
        except KeyError:
            pass

    return handler


async def start_tasker_server(
    handle_task_callback: Callable[[TaskCallbackData], None],
):
    app = aio_web.Application()
    task_callback_handler = create_aio_task_callback_handler(handle_task_callback)
    app.add_routes([aio_web.post("/task-callback", task_callback_handler)])
    runner = aio_web.AppRunner(app)
    await runner.setup()
    site = aio_web.TCPSite(runner, port=HTTP_PORT)
    await site.start()


async def start_tasker_server_for_futures(
    callback_futures: CallbackFutures,
):
    handle_task_callback = create_futures_task_callback_handler(callback_futures)
    await start_tasker_server(handle_task_callback)


if __name__ == "__main__":

    def mock_handle_task_callback(callback_data: TaskCallbackData):
        print(f"Received callback: {callback_data}")

    asyncio.run(start_tasker_server(mock_handle_task_callback))
