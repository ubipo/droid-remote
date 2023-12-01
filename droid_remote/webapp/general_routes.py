import asyncio
from typing import Callable, Optional
from aiohttp.web import Request, post
import html
import logging

from ..lxml_utils import element_to_string
from ..tasker import CallbackFutures
from ..device import adb, termux, tasker, high_level


logger = logging.getLogger(__name__)


async def set_screen_brightness(request: Request):
    form_data = await request.post()
    brightness = int(str(form_data.get("brightness", 0)))
    await termux.set_screen_brightness(brightness)
    return f"Set screen brightness to {brightness}"


async def wake_via_tasker(callback_futures: CallbackFutures):
    await tasker.wake_up_and_unlock(callback_futures)
    return "<img class='small' src='/static/awoken.jpg' />"


async def wake_via_adb():
    await adb.wake_up()
    return "<img class='small' src='/static/awoken.jpg' />"


async def read_screen():
    screen = await adb.read_screen_hierarchy()
    screen_xml = element_to_string(screen)
    return f"<pre>{html.escape(screen_xml)}</pre>"


adb_keep_alive_task: Optional[asyncio.Task] = None


async def get_adb_keep_alive():
    if adb_keep_alive_task is not None:
        try:
            adb_keep_alive_task.result()
        except asyncio.InvalidStateError:
            pass
        except asyncio.CancelledError:
            return "ADB keep-alive task cancelled."
        except Exception as e:
            return f"ADB keep-alive task failed: {e}"
        return "ADB keep-alive task is running."
    return "ADB keep-alive task is not running."


async def start_adb_keep_alive():
    global adb_keep_alive_task
    if adb_keep_alive_task is not None and not adb_keep_alive_task.done():
        return "ADB keep-alive is already running."
    adb_keep_alive_task = asyncio.create_task(adb.send_periodic_keep_alive())
    def done_callback(task: asyncio.Task):
        try:
            task.result()
        except asyncio.CancelledError:
            logger.info("ADB keep-alive task cancelled.")
        except Exception as e:
            logger.exception(f"ADB keep-alive task failed: {e}")
    
    adb_keep_alive_task.add_done_callback(done_callback)
    return "Started ADB keep-alive task."


def create_routes(tasker_callback_futures: CallbackFutures):
    device_handlers: dict[str, Callable] = {
        "adb-connect": lambda: high_level.adb_pair_and_connect(tasker_callback_futures),
        "adb-list-devices": adb.list_devices,
        "wake-via-adb": wake_via_adb,
        "wake-via-tasker": lambda: wake_via_tasker(tasker_callback_futures),
        "battery-status": termux.query_battery_status,
        "wake-lock": termux.wake_lock,
        "wake-unlock": termux.wake_unlock,
        "idle-info": termux.query_idle_info,
        "reboot": adb.reboot,
        "set-screen-brightness": set_screen_brightness,
        "start-tasker": termux.start_tasker,
        "start-tailscale-vpnservice": termux.start_tailscale_vpnservice,
        "get-vpn-ip-addresses": termux.get_vpn_interface,
        "ensure-ready-for-action": lambda: high_level.ensure_ready_for_action(tasker_callback_futures),
    }
    screen_handlers: dict[str, Callable] = {
        "read-screen": read_screen,
        "go-home": termux.go_home,
    }
    persistent_task_handlers: dict[str, Callable] = {
        "get-adb-keep-alive": get_adb_keep_alive,
        "start-adb-keep-alive": start_adb_keep_alive,
    }
    post_handlers = device_handlers | screen_handlers | persistent_task_handlers
    return [post(name, handler) for name, handler in post_handlers.items()]
