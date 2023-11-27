import logging
from pathlib import Path
import inspect
from jinja2 import Environment, FileSystemLoader, select_autoescape
from aiohttp.web import (
    Response,
    Request,
    Application,
    AppRunner,
    TCPSite,
    WebSocketResponse,
)
from aiohttp import web
from aiohttp_basicauth import BasicAuthMiddleware
import prometheus_client
from .itsme.known_actions import read_itsme_known_actions
from .itsme.routes import create_routes as create_itsme_routes
from .aio_util import prefix_all, wrap_all
from ..event_bus import EventBus
from .exception_handling import with_exception_handling
from .general_routes import create_routes as create_general_routes
from ..tasker import CallbackFutures
from ..config import ServerConfig


logger = logging.getLogger(__name__)


async def handle_root(jinja_env: Environment):
    return Response(
        body=jinja_env.get_template("daemon.html").render(
            {
                "itsme_known_actions": read_itsme_known_actions(),
            }
        ),
        content_type="text/html",
    )


async def handle_ws(event_bus: EventBus, request: Request):
    ws = WebSocketResponse()
    await ws.prepare(request)
    async for event in event_bus:
        try:
            await ws.send_str(
                inspect.cleandoc(
                    f""""
                        <pre id="log" hx-swap-oob="beforeend">
                        {event}
                        </pre>
                    """
                )
            )
        except ConnectionResetError:
            break


def handle_metrics(_: Request):
    return Response(text=prometheus_client.generate_latest().decode())


async def start_webapp(
    event_bus: EventBus,
    config: ServerConfig,
    tasker_callback_futures: CallbackFutures,
):
    logger.info("Creating and starting webapp...")
    template_dir = Path(__file__).parent / "templates"
    jinja_env = Environment(
        loader=FileSystemLoader(template_dir), autoescape=select_autoescape()
    )
    static_path = Path(__file__).parent / "static"

    itsme_pin = config.itsme_pin
    app_routes = [
        *prefix_all(create_itsme_routes(itsme_pin), "/itsme/"),
        *prefix_all(create_general_routes(tasker_callback_futures), "/"),
    ]
    secure_routes = [
        web.get("/", lambda _: handle_root(jinja_env)),
        web.get("/ws", lambda request: handle_ws(event_bus, request)),
        *wrap_all(app_routes, with_exception_handling),
    ]
    http_basic_password = config.http_basic_password
    if http_basic_password is not None:
        auth = BasicAuthMiddleware(
            username="admin", password=http_basic_password, force=False
        )
        authenticated_routes = wrap_all(secure_routes, auth.required)
    else:
        authenticated_routes = secure_routes
    routes = [
        web.get("/metrics", handle_metrics),
        web.static("/static", static_path),
        *authenticated_routes,
    ]

    app = Application()
    app.add_routes(routes)
    runner = AppRunner(app)
    await runner.setup()
    site = TCPSite(runner, "localhost", 8080)
    await site.start()
    logger.info("Webapp started")
    return site
