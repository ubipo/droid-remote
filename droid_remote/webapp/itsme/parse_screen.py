from typing import Callable
import inspect
import asyncio
from aiohttp.web import Request, post

from itsme_adb import driver
from .html import screen_to_html
from ..aio_util import call_with_request_kwargs, get_bool_form_value


async def handle_parse_action(itsme_pin: str, action: Callable, request: Request):
    result = await call_with_request_kwargs(action, request)
    form_data = await request.post()
    auto_tap_card = get_bool_form_value(form_data, "auto-tap-card")
    auto_enter_pin = get_bool_form_value(form_data, "auto-enter-pin")
    auto_dismiss_expired = get_bool_form_value(form_data, "auto-dismiss-expired")
    if isinstance(result, driver.PendingActionsHomeScreen) and auto_tap_card:
        await result.tap_card()
        await asyncio.sleep(1)
        return await handle_parse_action(itsme_pin, action, request)
    if isinstance(result, driver.PinpadScreen) and auto_enter_pin:
        await result.enter_pin(itsme_pin)
        await asyncio.sleep(1)
        return await handle_parse_action(itsme_pin, action, request)
    if isinstance(result, driver.ActionExpiredScreen) and auto_dismiss_expired:
        await result.ok()
        await asyncio.sleep(1)
        return await handle_parse_action(itsme_pin, action, request)
    if isinstance(result, driver.PlayRatingScreen):
        await result.not_now()
        await asyncio.sleep(1)
        return await handle_parse_action(itsme_pin, action, request)

    return inspect.cleandoc(
        f"""
    <p>Found screen:</p>
    {screen_to_html(result)}
  """
    )


def create_routes(itsme_pin: str):
    handlers = {
        "any": driver.parse_any_screen,
        "home": driver.parse_home_screen,
        "action": driver.parse_action_screen,
        "post-confirm": driver.parse_post_confirm_screen,
    }
    def wrap_handler(handler):
        return lambda request: handle_parse_action(itsme_pin, handler, request)
    return [post(name, wrap_handler(handler)) for name, handler in handlers.items()]
