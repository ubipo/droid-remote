from aiohttp.web import post
from . import parse_screen
from . import screen_action
from .confirm_known_action import handle_confirm_known_action
from itsme_adb import driver
from ..aio_util import prefix_all


def create_routes(itsme_pin: str):
    return [
        post("launch", lambda _: driver.launch()),
        post("force-stop", lambda _: driver.force_stop()),
        post("confirm-known-action", lambda request: handle_confirm_known_action(
            itsme_pin,
            request,
        )),
        *prefix_all(parse_screen.create_routes(itsme_pin), "parse-screen/"),
        *prefix_all(screen_action.create_routes(itsme_pin), "screen-action/"),
    ]
