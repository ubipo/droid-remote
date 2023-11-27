import logging
import asyncio
from asyncio.tasks import Task
import math
from asyncio import Future
import time
import argparse
from typing import Optional
from prometheus_client import Info
from dotenv import load_dotenv
from .event_bus import EventBus
from .ngrok import run_ngrok
from .webapp import start_webapp
from .tasker import start_tasker_server_for_futures
from .config import populate_server_arg_parser, safe_generate, generate_server_config_from_args, ServerConfig
from .pid_management import clear_pid_files, ensure_no_existing_process_or_exit, init_pid_files
from .env_util import fix_env_login_variables
from .device import high_level
from .dataclasses_json_conf import configure_dataclasses_json
from .log_setup import setup_logging
from .signal_handling import add_signal_handlers


logger = logging.getLogger(__name__)


async def run_server(event_bus: EventBus, config: ServerConfig):
    logger.info("Starting droid remote server...")
    fix_env_login_variables()
    running_tasks: list[Task] = []
    add_signal_handlers(running_tasks)
    ngrok_domain = config.ngrok_domain
    if ngrok_domain is not None:
        ngrok_task = asyncio.create_task(
            run_ngrok(ngrok_domain, config.child_pgids_file_path)
        )
        running_tasks.append(ngrok_task)
    tasker_callback_futures: dict[str, Future] = {}
    await start_webapp(event_bus, config, tasker_callback_futures)
    await start_tasker_server_for_futures(tasker_callback_futures)
    if config.ensure_ready_for_action:
        await high_level.ensure_ready_for_action(tasker_callback_futures)
    logger.info("All tasks started.")
    if len(running_tasks) > 0:
        await asyncio.wait(running_tasks)
    else:
        await Future()


def main(config: Optional[ServerConfig] = None):
    configure_dataclasses_json()

    if config is None:
        load_dotenv()
        parser = argparse.ArgumentParser()
        populate_server_arg_parser(parser)
        args = parser.parse_args()
        config = safe_generate(args, generate_server_config_from_args)

    ensure_no_existing_process_or_exit(config.pid_file_paths, config.daemon_name)
    init_pid_files(config.pid_file_paths)

    start_time = math.floor(time.time())
    prometheus_process_info = Info("process", "Daemon process info")
    prometheus_process_info.info({ "start_time": str(start_time) })

    event_bus = EventBus()
    setup_logging(config.log_file_path, event_bus)
    try:
        asyncio.run(run_server(event_bus, config))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.exception(
            f"Unhandled exception in server: '{e}'. Waiting for loop to finish and exiting..."
        )
    finally:
        clear_pid_files(config.pid_file_paths)
