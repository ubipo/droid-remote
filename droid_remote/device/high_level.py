import logging
from . import adb, termux, tasker
from .tasker import CallbackFutures


logger = logging.getLogger(__name__)


async def adb_pair_and_connect(tasker_callback_futures: CallbackFutures):
    logger.debug("Enabling wireless adb and pairing...")
    task_result = await tasker.wireless_adb_enable_and_pair(tasker_callback_futures)
    logging.debug(f"Wireless adb enable and pair result: {task_result}")
    pair_status, pair_details = task_result.split(" ", 1)
    if pair_status != "success":
        logger.warning(f"Failed to pair: {pair_status} {pair_details}")
        return f"Failed to pair: {pair_status} {pair_details}"
    adb_host = pair_details
    logger.debug(f"Connecting to adb at {adb_host}...")
    await adb.disconnect()
    connect_result = await adb.connect(adb_host)
    return f"Connected to adb: {connect_result}"


async def ensure_ready_for_action(tasker_callback_futures: CallbackFutures):
    """Catch-all function to ensure the device is ready for action.
    - Enables wake lock
    - Wakes up the screen and sets brightness
    - Connects to adb
    - Starts TailScale VPN
    """
    logger.debug("Ensuring device is ready for action...")
    await termux.wake_lock()
    await tasker.wake_up_and_unlock(tasker_callback_futures)
    await termux.set_screen_brightness(1)
    await adb_pair_and_connect(tasker_callback_futures)
    await termux.start_tailscale_vpnservice()
    logger.debug("Device is ready for action")
    return "Device is ready for action"
