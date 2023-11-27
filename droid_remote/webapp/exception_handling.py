import traceback
import logging
import sys
from typing import Callable
from html import escape as html_escape
from aiohttp.web import Request, Response
from .aio_util import call_with_request_kwargs
from itsme_adb.driver import WrongScreenError
from ..tasker import TaskTimeoutException
from ..lxml_utils import element_to_string


logger = logging.getLogger(__name__)


def with_exception_handling(async_fn: Callable):
    async def handler(request: Request):
        try:
            response = await call_with_request_kwargs(async_fn, request)
        except TaskTimeoutException as e:
            logger.warning(f"Tasker task timed out: {e}")
            return Response(text=f"Tasker task timed out: {e}")
        except WrongScreenError as e:
            logger.warning(f"Wrong screen: {e.message} {len(e.parsers_tried)=}")
            causes_html = (
                f"""
                    <p>Causes:</p>
                    <ul>
                        {"".join(
                            f"<li>{name}: {html_escape(error.message)}</li>"
                            for name, error in e.parsers_tried.items()
                        )}
                    </ul>
                """
                if len(e.parsers_tried) > 0
                else ""
            )
            return Response(
                text=f"""
                    <p>Wrong screen: {e.message}</p>
                    <p>Screen hierarchy:</p>
                    <pre>{html_escape(element_to_string(e.screen))}</pre>
                    {causes_html}
                """,
                status=500,
            )
        except Exception:
            logger.error(
                f"Unhandled exception in {async_fn.__name__} while handling webapp request:",
                exc_info=True,
            )
            try:
                function_name = async_fn.__name__
            except AttributeError:
                function_name = "nameless function"
            return Response(
                text=f"""
          <p>Unhandled exception in {function_name}:</p>
          <p>{html_escape(str(sys.exc_info()[1]))}</p>
          <pre>{html_escape(traceback.format_exc())}</pre>
        """,
                status=500,
            )

        return Response(text=str(response))

    return handler
