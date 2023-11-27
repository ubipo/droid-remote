import getpass
import logging
import os
import pwd
from typing import Callable


logger = logging.getLogger(__name__)


def set_env_if_unset(env: dict[str, str], get_value: Callable[[], str], key: str):
    if env.get(key) is None:
        value = get_value()
        logger.warning(
            f"Environment variable '{key}' not set. Setting it to '{value}'."
        )
        env[key] = value


def fix_env_login_variables():
    """Termux:Tasker omits some common environment variables when running scripts.
    Ngrok for example requires USER to be set.
    This function adds them back to the current environment if they are missing.
    """
    env = os.environ.copy()
    set_env_if_unset(env, getpass.getuser, "USER")
    set_env_if_unset(env, lambda: pwd.getpwuid(os.getuid()).pw_shell, "SHELL")
    set_env_if_unset(env, lambda: pwd.getpwuid(os.getuid()).pw_name, "LOGNAME")
    return env
