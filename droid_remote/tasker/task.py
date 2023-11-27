import asyncio
import logging
from secrets import token_hex
import subprocess
from typing import Optional
from .exceptions import TaskTimeoutException
from .model import CallbackFuture, CallbackFutures


logger = logging.getLogger(__name__)


async def execute_tasker_task(
    callback_futures: CallbackFutures,
    task_name,
    param2: Optional[str] = None,
    timeout=5,
):
    logger.debug(f"Executing tasker task {task_name} with param2={param2}")
    await asyncio.sleep(1)
    correlation_id = token_hex(8)
    broadcast_result = subprocess.run(
        [
            "am",
            "broadcast",
            "-a",
            "net.dinglisch.android.taskerm.EXECUTE_TASK",
            "-e",
            "task_name",
            task_name,
            "-e",
            "task_par1_a",
            correlation_id,
            "-e",
            "task_par2_a",
            param2 or "",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if broadcast_result.returncode != 0:
        raise Exception(
            f'Broadcasting tasker task failed: returncode={broadcast_result.returncode} stderr={broadcast_result.stderr.decode("utf-8")}'
        )
    logger.debug(
        f"Broadcasted tasker task {task_name} with correlation_id={correlation_id}"
    )
    callback_future: CallbackFuture = asyncio.Future()
    callback_futures[correlation_id] = callback_future
    try:
        async with asyncio.timeout(10):
            logger.debug(f"Waiting for tasker task {task_name} to complete")
            result = await callback_future
            logger.debug(f"Tasker task '{task_name}' completed with result '{result}'")
            return result
    except TimeoutError:
        raise TaskTimeoutException(correlation_id, task_name, timeout)
    finally:
        try:
            del callback_futures[correlation_id]
        except KeyError:
            pass


async def cli_test():
    logging.basicConfig(level=logging.DEBUG)
    # callback_futures = {}
    # loop = asyncio.get_running_loop()
    # ipc_listen_task = asyncio.create_task(asyncio.to_thread(
    #   ipc_listen_forever, callback_futures
    # ))
    # try:
    #   task_result = await execute_tasker_task(callback_futures, 'dummy_task', 'aaa')
    # except:
    #   logger.error("Error executing tasker task", exc_info=True)
    #   return
    # finally:
    #   ipc_listen_task.cancel()
    # print(task_result)


if __name__ == "__main__":
    asyncio.run(cli_test())
