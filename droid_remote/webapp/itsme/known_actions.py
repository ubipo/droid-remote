import logging
from pathlib import Path
from dataclasses import dataclass
from dataclasses_json import dataclass_json, LetterCase, DataClassJsonMixin


ITSME_KNOWN_ACTIONS_PATH = Path(__file__).parent / "itsme_known_actions.json"
logger = logging.getLogger(__name__)


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class KnownItsmeActions(DataClassJsonMixin):
    app_actions: dict[str, set[str]]


def read_itsme_known_actions() -> KnownItsmeActions:
    try:
        with open(ITSME_KNOWN_ACTIONS_PATH, "r") as f:
            json = f.read()
            if len(json) > 0:
                return KnownItsmeActions.from_json(json)
    except FileNotFoundError:
        pass

    return KnownItsmeActions(app_actions={})


def save_itsme_action(app: str, action: str):
    logger.info(f"Saving itsme action: {app} {action}")

    known_apps = read_itsme_known_actions()

    if app not in known_apps.app_actions:
        known_apps.app_actions[app] = set()

    known_apps.app_actions[app].add(action)

    with open(ITSME_KNOWN_ACTIONS_PATH, "w") as f:
        f.write(known_apps.to_json())
