import asyncio
import dataclasses
import logging
from typing import Optional
from .pid_management import PidFilePaths, clear_pid_files, ensure_no_existing_process_or_exit, init_pid_files
from .config import CtlConfig
from .health import safe_check_if_daemon_healthy
from .signal_handling import add_signal_handlers
from .daemon_management import restart_daemon


HEALTH_CHECK_TIMEOUT = 5
HEALTH_CHECK_REPEAT_UNHEALTHY_TIMEOUT = 30
logger = logging.getLogger(__name__)


async def restart_if_unhealthy(
    base_url: str,
    config: CtlConfig,
    pid_file_paths: PidFilePaths,
    was_healthy: Optional[bool],
):
    is_healthy = safe_check_if_daemon_healthy(pid_file_paths, base_url)
    if not is_healthy:
        if was_healthy is False:
            logger.warning("Server is still not healthy. Restarting again...")
        elif was_healthy:
            logger.warning("Server has become unhealthy. Restarting...")
        else:
            logger.warning("Server is unhealthy. Restarting...")
        await restart_daemon(config)
    elif was_healthy is False:
        logger.info("Server has healed back to perfect health.")
    return is_healthy


async def watch_forever(config: CtlConfig):
    # We are the watchdog, indicate that what we are controlling is the server
    server_config = dataclasses.replace(config, watchdog=False)
    server_pid_file_paths = server_config.pid_file_paths
    is_healthy: Optional[bool] = None
    while True:
        was_healthy = is_healthy
        is_healthy = await restart_if_unhealthy(
            config.monitoring_base_url, server_config, server_pid_file_paths, was_healthy
        )
        if was_healthy is None:
            if is_healthy:
                logger.info("Server was already healthy, continuing to monitor...")
            else:
                logger.info("Continuing to monitor...")
        restart_loop = is_healthy is False and was_healthy is False
        await asyncio.sleep(
            HEALTH_CHECK_REPEAT_UNHEALTHY_TIMEOUT
            if restart_loop
            else HEALTH_CHECK_TIMEOUT
        )


async def run_watchdog(config: CtlConfig):
    logger.info("Starting droid remote watchdog...")
    watch_forever_task = asyncio.create_task(watch_forever(config))
    add_signal_handlers([watch_forever_task])
    await watch_forever_task
    


def main(config: CtlConfig):
    pid_file_paths = config.pid_file_paths
    ensure_no_existing_process_or_exit(
        pid_file_paths,
        config.daemon_name,
        config.treat_kill_permission_error_as_not_running,
    )
    init_pid_files(pid_file_paths)
    try:
        asyncio.run(run_watchdog(config))
    except asyncio.CancelledError:
        pass
    finally:
        clear_pid_files(pid_file_paths)
