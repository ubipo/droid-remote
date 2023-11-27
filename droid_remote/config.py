import argparse
import dataclasses
from dataclasses import dataclass
from enum import Enum, auto
from functools import cached_property, cache
import os
from pathlib import Path
import sys
from tempfile import mkstemp
from typing import Callable, Optional, TypeVar, Union
from dataclasses_json import dataclass_json, DataClassJsonMixin
from .pid_management import PidFilePaths


ENV_VAR_PREFIX = "DR_"
FOREGROUND_SUBCOMMAND = "foreground"


@dataclass_json
@dataclass(frozen=True, kw_only=True)
class ServerConfig(DataClassJsonMixin):
    log_file_path: Path
    pid_file_path: Path
    child_pgids_file_path: Path
    ngrok_agent_pid_file_path: Path
    itsme_pin: str
    http_basic_password: Optional[str] = None
    ngrok_domain: Optional[str] = None
    ensure_ready_for_action: bool = False

    @property
    def daemon_name(self):
        return "droid remote server"
    
    @property
    def daemon_name_cap(self):
        return self.daemon_name.capitalize()

    @cached_property
    def pid_file_paths(self):
        return PidFilePaths(self.pid_file_path, self.child_pgids_file_path)


@dataclass(frozen=True, kw_only=True)
class CtlConfig(ServerConfig):
    ctl_log_file_path: Path
    watchdog_pid_file_path: Path
    watchdog: bool = False
    monitoring_base_url: str

    @property
    def daemon_name(self):
        return "watchdog" if self.watchdog else super().daemon_name

    @cached_property
    def pid_file_paths(self):
        if self.watchdog:
            return PidFilePaths(self.watchdog_pid_file_path)
        else:
            return PidFilePaths(self.pid_file_path, self.child_pgids_file_path)


Config = Union[ServerConfig, CtlConfig]


def test_writable(path: Path):
    try:
        _, tempfile = mkstemp(dir=path)
    finally:
        try:
            os.remove(tempfile)
        except (FileNotFoundError, UnboundLocalError):
            return False
    return True


def get_root_dir():
    root = Path("/")
    if test_writable(root / "tmp"):
        return root
    prefix_str = os.environ.get("PREFIX", "")
    if len(prefix_str) > 0:
        prefix = Path(prefix_str)
        if prefix.is_dir() and test_writable(prefix / "tmp"):
            return prefix
    home = Path("/home")
    if test_writable(home / "tmp"):
        return home
    cwd = Path.cwd()
    if test_writable(cwd):
        return cwd
    raise Exception("Could not find writable directory.")


@dataclass
class MissingConfigValueException(Exception):
    name: str


def throw_on_missing_config_value(name: str):
    def get_default():
        raise MissingConfigValueException(name)
    return get_default


T_ARG_VALUE = TypeVar("T_ARG_VALUE", bound=str | int | bool | None)


def arg_env_or(
    args: argparse.Namespace,
    name: str,
    default_or_getter: Callable[[], T_ARG_VALUE] | T_ARG_VALUE,
    convert_from_str: Optional[Callable[[str], T_ARG_VALUE]] = None,
) -> T_ARG_VALUE:
    from_args: T_ARG_VALUE = getattr(args, name)
    if from_args is None:
        env_name = f"{ENV_VAR_PREFIX}{name.upper()}"
        from_env = os.environ.get(f"{env_name}")
        if from_env is None:
            if callable(default_or_getter):
                return default_or_getter()
            else:
                return default_or_getter
        elif convert_from_str is not None:
            return convert_from_str(from_env)
        else:
            raise RuntimeError(f"Cannot parse environment variable {env_name}")
    return from_args


T_STR_DEFAULT = TypeVar("T_STR_DEFAULT", bound=str | None)
def str_arg_env_or(
    args: argparse.Namespace,
    name: str,
    default_or_getter: Callable[[], T_STR_DEFAULT] | T_STR_DEFAULT,
) -> T_STR_DEFAULT:
    return arg_env_or(args, name, default_or_getter, lambda s: s)


T_INT_DEFAULT = TypeVar("T_INT_DEFAULT", bound=int | None)
def int_arg_env_or(
    args: argparse.Namespace,
    name: str,
    default_or_getter: Callable[[], T_INT_DEFAULT] | T_INT_DEFAULT,
) -> T_INT_DEFAULT:
    return arg_env_or(args, name, default_or_getter, lambda s: int(s))


T_BOOL_DEFAULT = TypeVar("T_BOOL_DEFAULT", bound=bool | None)
def bool_arg_env_or(args: argparse.Namespace, name: str, default_or_getter: Callable[[], T_BOOL_DEFAULT] | T_BOOL_DEFAULT,):
    return arg_env_or(args, name, default_or_getter, lambda s: s.lower() in ["true", "yes", "1", "y", "on"])


@cache
def generate_defaults():
    root_dir = get_root_dir()
    var = root_dir / "var"
    return CtlConfig(
        log_file_path=var / "log" / "droid_remote.log",
        pid_file_path=var / "run" / "droid_remote.pid",
        child_pgids_file_path=var / "run" / "droid_remote_child_pgids.txt",
        ngrok_agent_pid_file_path=var / "run" / "droid_remote_ngrok_agent.pid",
        # Will simply generate a RuntimeError when attempting to use
        itsme_pin="",
        ctl_log_file_path=var / "log" / "droid_remote_ctl.log",
        watchdog_pid_file_path=var / "run" / "droid_remote_watchdog.pid",
        monitoring_base_url="http://localhost:8080",
    )


def generate_server_config_from_args(args: argparse.Namespace):
    defaults = generate_defaults()
    config_json = getattr(args, "config_json")
    if config_json is not None:
        return ServerConfig.from_json(config_json)
    pid_file_path = Path(str_arg_env_or(args, "pid_file", defaults.pid_file_path))
    child_pgids_file_path = Path(
        str_arg_env_or(args, "child_pgids_file", defaults.child_pgids_file_path)
    )
    log_file_path = Path(str_arg_env_or(args, "log_file", defaults.log_file_path))
    itsme_pin = str_arg_env_or(args, "itsme_pin", throw_on_missing_config_value("itsme_pin"))
    http_basic_password: str | None = str_arg_env_or(args, "http_basic_password", None)
    if len(str(http_basic_password).strip()) == 0:
        http_basic_password = None
    ngrok_domain = str_arg_env_or(args, "ngrok_domain", defaults.ngrok_domain)
    ensure_ready_for_action = bool_arg_env_or(
        args, "ensure_ready_for_action", defaults.ensure_ready_for_action
    )
    return ServerConfig(
        log_file_path=log_file_path,
        pid_file_path=pid_file_path,
        child_pgids_file_path=child_pgids_file_path,
        ngrok_agent_pid_file_path=defaults.ngrok_agent_pid_file_path,
        itsme_pin=itsme_pin,
        http_basic_password=http_basic_password,
        ngrok_domain=ngrok_domain,
        ensure_ready_for_action=ensure_ready_for_action,
    )


def generate_ctl_config_from_args(args: argparse.Namespace):
    defaults = generate_defaults()
    config_json = getattr(args, "config_json")
    if config_json is not None:
        return CtlConfig.from_json(config_json)
    server_config = generate_server_config_from_args(args)
    watchdog = bool_arg_env_or(args, "watchdog", defaults.watchdog)
    watchdog_pid_file_path = Path(str_arg_env_or(
        args, "watchdog_pid_file", defaults.watchdog_pid_file_path
    ))
    monitor_ngrok_domain = bool_arg_env_or(args, "monitor_ngrok_domain", False)
    monitoring_base_url = str_arg_env_or(args, "monitoring_base_url", None)
    if monitor_ngrok_domain and monitoring_base_url is not None:
        raise ValueError("Cannot specify both --monitor-ngrok-domain and --monitoring-base-url")
    elif monitor_ngrok_domain:
        ngrok_domain = server_config.ngrok_domain
        if ngrok_domain is None:
            raise ValueError("Cannot specify --monitor-ngrok-domain without --ngrok-domain")
        monitoring_base_url = f"https://{ngrok_domain}"
    elif monitoring_base_url is None:
        monitoring_base_url = defaults.monitoring_base_url
    ctl_log_file_path = Path(str_arg_env_or(
        args, "ctl_log_file", defaults.ctl_log_file_path
    ))
    return CtlConfig(
        **dataclasses.asdict(server_config),
        ctl_log_file_path=ctl_log_file_path,
        watchdog=watchdog,
        watchdog_pid_file_path=watchdog_pid_file_path,
        monitoring_base_url=monitoring_base_url,
    )


GeneratedConfig = TypeVar("GeneratedConfig", ServerConfig, CtlConfig)


def safe_generate(args: argparse.Namespace, generator: Callable[[argparse.Namespace], GeneratedConfig]):
    try:
        return generator(args)
    except MissingConfigValueException as e:
        cli_name = e.name.replace("_", "-")
        env_name = f"{ENV_VAR_PREFIX}{e.name.upper()}"
        print(f"Configuration value '{e.name}' is required. Specify it as an argument ({cli_name}) or as an environment variable ({env_name}).", file=sys.stderr)
        sys.exit(1)


def populate_server_arg_parser(parser: argparse.ArgumentParser):
    defaults = generate_defaults()
    parser.add_argument(
        "--pid-file",
        help=f"Path to PID file. Default: {defaults.pid_file_path}",
    )
    parser.add_argument(
        "--child-pgids-file",
        help="Path to child PGIDs file",
    )
    parser.add_argument(
        "--log-file",
        help="Path to log file",
    )
    parser.add_argument(
        "--ngrok-domain",
        default=None,
        help="Domain to use for ngrok",
    )
    parser.add_argument(
        "--itsme-pin",
        default=None,
        help="PIN for itsme",
    )
    parser.add_argument(
        "--http-basic-password",
        default=None,
        help="Password for HTTP basic auth",
    )
    parser.add_argument(
        "--ensure-ready-for-action",
        action="store_true",
        help="Ensure that the device is ready for action on server start",
    )
    parser.add_argument(
        "--config-json",
        default=None,
        help="Droid Remote config as JSON. Overrides all other arguments.",
    )


class CtlActions(Enum):
    FOREGROUND = auto()
    STATUS = auto()
    START = auto()
    RESTART = auto()
    STOP = auto()
    FORCE_STOP = auto()

    @property
    def cli_name(self):
        return self.name.lower().replace("_", "-")


def populate_ctl_arg_parser(parser: argparse.ArgumentParser):
    populate_server_arg_parser(parser)
    parser.add_argument(
        "action",
        choices=[action.cli_name for action in CtlActions],
        help="Action to perform.",
    )
    parser.add_argument(
        "--watchdog",
        action="store_true",
        help="Run the watchdog instead of the droid remote server.",
    )
    parser.add_argument(
        "--watchdog-pid-file",
        default=None,
        help="Path to watchdog PID file.",
    )
    parser.add_argument(
        "--monitoring-base-url",
        help="Server base URL to monitor for health.",
    )
    parser.add_argument(
        "--monitor-ngrok-domain",
        action="store_true",
        default=None,
        help="Use 'https://{ngrok_domain}' as the base URL for monitoring.",
    )
    parser.add_argument(
        "--ctl-log-file",
        default=None,
        help="Path to ctl log file",
    )
