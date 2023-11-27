import asyncio
from typing import Callable
from aiohttp.web import Request, post

from itsme_adb import driver
from .parse_screen import handle_parse_action
from ..aio_util import call_with_request_kwargs


async def handle_itsme_screen_action(itsme_pin: str, action: Callable, request: Request):
    result = await call_with_request_kwargs(action, request)
    if result is not None:
        return f"<p>Result from action: {str(result)}</p>"

    # Wait for the screen to change
    await asyncio.sleep(1)
    return await handle_parse_action(itsme_pin, driver.parse_any_screen, request)


async def poka_yoke_tap_image(request: Request):
    image_number = int(request.query["image_number"])
    return await driver.poka_yoke_screen_tap_image(image_number)


async def pinpad_enter_pin(itsme_pin: str):
    return await driver.pinpad_screen_enter_pin(itsme_pin)


def create_routes(itsme_pin: str):
    handlers: dict[str, Callable] = {
        "home-tap-card": driver.home_screen_tap_card,
        "action-confirm": driver.action_screen_confirm,
        "action-reject": driver.action_screen_reject,
        "action-expired-ok": driver.action_expired_screen_ok,
        "poka-yoke-tap-image": poka_yoke_tap_image,
        "pinpad-enter-pin": lambda: pinpad_enter_pin(itsme_pin),
        "play-rating-not-now": driver.play_rating_screen_not_now,
    }
    def wrap_handler(handler):
        return lambda request: handle_itsme_screen_action(itsme_pin, handler, request)
    return [post(name, wrap_handler(handler)) for name, handler in handlers.items()]
