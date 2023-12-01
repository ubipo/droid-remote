#!/data/data/com.termux/files/usr/bin/python

import logging
import sys
import argparse
import asyncio
from dotenv import load_dotenv
from .daemon_management import start_daemon, restart_daemon, stop_daemon, force_stop_daemon, ExitedBeforeFirstLogLineError
from .dataclasses_json_conf import configure_dataclasses_json
from .pid_management import PidFilePaths, read_pid, check_if_process_running
from .config import ServerConfig, CtlConfig, safe_generate, generate_ctl_config_from_args, populate_ctl_arg_parser, CtlActions
from .log_setup import setup_logging
from .health import check_daemon_health_http, DaemonHealthCheckError


logger = logging.getLogger(__name__)


def status_server_daemon(config: CtlConfig):
    pid = read_pid(config.pid_file_paths.daemon_pid)
    process_healthy = check_if_process_running(
        pid,
        config.treat_kill_permission_error_as_not_running,
    )
    http_healthy = check_daemon_health_http(config.monitoring_base_url)
    if not process_healthy and not http_healthy:
        logger.info("Server not running")
        return
    elif not http_healthy:
        logger.info("Server process running but not healthy")
        return
    elif not process_healthy:
        logger.error("Server process but somehow still responding. Inconsistent state.")
        sys.exit(1)

    logger.info("Server running and healthy")
        

def status_watchdog_daemon(config: CtlConfig):
    pid = read_pid(config.pid_file_paths.daemon_pid)
    process_healthy = check_if_process_running(
        pid,
        config.treat_kill_permission_error_as_not_running,
    )
    if not process_healthy:
        logger.info("Watchdog not running")
        return
    
    logger.info("Watchdog running")


def run_server_foreground(config: ServerConfig):
    from .server import main as server_main
    server_main(config)


def run_watchdog_foreground(config: CtlConfig):
    from .watchdog import main as watchdog_main
    watchdog_main(config)


def main():
    configure_dataclasses_json()
    load_dotenv()

    arg0 = sys.argv[0]
    if arg0.endswith("__main__.py"):
        arg0 = "python -m droid_remote"
    parser = argparse.ArgumentParser(
        prog=arg0,
        description="Control the Droid Remote server daemon.",
    )
    populate_ctl_arg_parser(parser)

    args = parser.parse_args()
    action = args.action
    config = safe_generate(args, generate_ctl_config_from_args)
    setup_logging(config.ctl_log_file_path, log_file_level=config.ctl_log_file_log_level)

    try:
        if action == CtlActions.FOREGROUND.cli_name:
            if config.watchdog:
                run_watchdog_foreground(config)
            else:
                run_server_foreground(config)
        elif action == CtlActions.STATUS.cli_name:
            if config.watchdog:
                status_watchdog_daemon(config)
            else:
                status_server_daemon(config)
        elif action == CtlActions.START.cli_name:
            asyncio.run(start_daemon(config))
        elif action == CtlActions.RESTART.cli_name:
            asyncio.run(restart_daemon(config))
        elif action == CtlActions.STOP.cli_name:
            stop_daemon(config)
        elif action == CtlActions.FORCE_STOP.cli_name:
            force_stop_daemon(config)
        else:
            print(f"Unknown action {action}", file=sys.stderr)
    except ExitedBeforeFirstLogLineError:
        print("Daemon exited before first log line.", file=sys.stderr)
    except DaemonHealthCheckError as e:
        print(f"Daemon health check failed: {e}", file=sys.stderr)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    main()
