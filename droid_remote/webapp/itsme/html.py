import inspect
from typing import Any
import html as lib_html
from urllib.parse import urlencode
from itsme_adb import driver
from .known_actions import save_itsme_action


def html_escape(text: str):
    escaped = lib_html.escape(text)
    return escaped.replace("\n", "<br />")


def itsme_hx_action_attrs(action: str, params: dict[str, Any] = {}):
    return f"""
        hx-post="/itsme/screen-action/{action}?{urlencode(params)}"
        hx-target="#itsme-results"
        hx-target-*="#itsme-errors"
        hx-indicator="#itsme-spinner"
    """


def itsme_button(action: str, title: str, params: dict[str, Any] = {}):
    return inspect.cleandoc(
        f"""
            <button {itsme_hx_action_attrs(action, params)}>
            {title}
            </button>
        """
    )


def basic_info_to_html(basic_info: driver.ActionBasicInfo):
    return inspect.cleandoc(
        f"""
            <p>{basic_info.action}</p>
            <p>{basic_info.app}</p>
            <p>{basic_info.time}</p>
        """
    )


def screen_to_html(screen: driver.Screen):
    if isinstance(screen, driver.NoPendingActionsHomeScreen):
        return "<h3>No pending actions</h3>"
    if isinstance(screen, driver.PendingActionsHomeScreen):
        return inspect.cleandoc(
            f"""
            <h3>Pending action</h3>
            {screen.action_count} pending actions:
            {basic_info_to_html(screen.basic_info)}
            {itsme_button('home-tap-card', 'Tap card')}
            """
        )
    if isinstance(screen, driver.ActionScreen):
        save_itsme_action(screen.basic_info.app, screen.basic_info.action)
        extra_info = f"""
            <h4>Extra info</h4>
            <ul>
                {"".join(f"<li>{html_escape(line)}</li>" for line in screen.extra_info)}
            </ul>
        """ if screen.extra_info else ""
        details = f"""
            <h4>Details</h4>
            <ul>
                {"".join(f"<li>{html_escape(line)}</li>" for line in screen.details)}
            </ul>
        """ if screen.details else ""
        return inspect.cleandoc(
            f"""
            <h3>Pending action confirmation</h3>
            {basic_info_to_html(screen.basic_info)}
            <h4>Shared data: </h4>
            <ul>
                {"".join(f"<li>{html_escape(line)}</li>" for line in screen.shared_data)}
            </ul>
            {extra_info}
            {details}
            {itsme_button('action-confirm', 'Confirm')}
            {itsme_button('action-reject', 'Reject')}
            """
        )
    if isinstance(screen, driver.PokaYokeScreen):
        return inspect.cleandoc(
            f"""
            <h3>Poka yoke</h3>
            {
                "".join(itsme_button(
                "poka-yoke-tap-image",
                f'''<img
                    src='https://mobileapp.itsme.be/poka-yoke/selected/Logo_Tan_{image.number:0>2}.svg'
                />''',
                {"image_number": image.number}
                )
                for image in screen.images)
            }
            """
        )
    if isinstance(screen, driver.PinpadScreen):
        return inspect.cleandoc(
            f"""
            <h3>Pin confirmation</h3>
            {itsme_button('pinpad-enter-pin', 'Enter PIN')}
            """
        )
    if isinstance(screen, driver.ActionExpiredScreen):
        return inspect.cleandoc(
            f"""
            <h3>Action expired</h3>
            {itsme_button('action-expired-ok', 'OK')}
            """
        )
    if isinstance(screen, driver.PlayRatingScreen):
        return inspect.cleandoc(
            f"""
            <h3>Play rating</h3>
            {itsme_button('play-rating-not-now', 'Not now')}
            """
        )
    if isinstance(screen, driver.ActionConfirmedScreen):
        return inspect.cleandoc("<h3>Action succesfully confirmed</h3>")
    raise Exception(f"Unknown itsme screen: {str(screen)}")
