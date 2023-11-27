from typing import Any, Callable
import inspect
from aiohttp.web import Request, RouteDef
from multidict import MultiDictProxy
import attrs


async def call_with_request_kwargs(fn: Callable, request: Request):
    kwargs: dict[str, Any] = {}
    parameters = inspect.signature(fn).parameters
    if parameters.get("request") is not None:
        kwargs["request"] = request
    if parameters.get("_") is not None:
        kwargs["_"] = None

    result = fn(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def get_bool_form_value(form_data: MultiDictProxy, key: str) -> bool:
    value = form_data.get(key)
    if not isinstance(value, str):
        return False
    return value.lower() in ["true", "1", "on"]


def add_prefix(route_def: RouteDef, prefix: str):
    return attrs.evolve(route_def, path=prefix + route_def.path)


def prefix_all(routes: list[RouteDef], prefix: str):
    return [add_prefix(route, prefix) for route in routes]


def wrap(route_def: RouteDef, wrapper: Callable[[Callable], Callable]):
    return attrs.evolve(route_def, handler=wrapper(route_def.handler))


def wrap_all(routes: list[RouteDef], wrapper: Callable[[Callable], Callable]):
    return [wrap(route, wrapper) for route in routes]
