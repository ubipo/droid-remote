import inspect
from aiohttp.web import Request
from .html import screen_to_html, itsme_button
from itsme_adb import driver


async def handle_confirm_known_action(itsme_pin: str, request: Request):
    app = request.query["app"]
    action = request.query["action"]
    retry_button = itsme_button(
        "confirm-known-action",
        f"Retry confirm known action '{app}: {action}'",
        {"app": app, "action": action},
    )
    try:
        return await driver.confirm_app_action(itsme_pin, app, action)
    except driver.ConfirmAppActionInteractionRequired as e:
        html = screen_to_html(e.screen)
        return inspect.cleandoc(
            f"""
            <p>Interaction required:</p>
            {html}
            {retry_button}
            """
        )
    except driver.NoPendingActionsException:
        return "<h3>No pending actions</h3>"
    except driver.UnexpectedPendingActionException as e:
        return inspect.cleandoc(
            f"""
            <h3>Unexpected pending action</h3>
            <p>Pending action: {e.wrong_basic_info.app}: {e.wrong_basic_info.action}</p>
            <p>Expected action: {app}: {action}</p>
            {retry_button}
            """
        )
