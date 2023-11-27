from droid_remote.tasker import execute_tasker_task, CallbackFutures


async def wake_up_and_unlock(callback_futures: CallbackFutures):
    return await execute_tasker_task(callback_futures, "ensure_unlocked")


async def wireless_adb_enable_and_pair(callback_futures: CallbackFutures):
    return await execute_tasker_task(callback_futures, "wireless_adb_enable_and_pair")
