import logging
import asyncio
from asyncio import subprocess
import signal
import sys
import os
from .pid_management import read_pid, read_child_pgids
from .config import CtlConfig, CtlActions


logger = logging.getLogger(__name__)


def send_kill_signal(
    config: CtlConfig,
    sig: signal.Signals,
):
    pid = read_pid(config.pid_file_paths.daemon_pid)
    pgids = read_child_pgids(config.pid_file_paths.child_pgids)
    if pid is None and len(pgids) == 0:
        logger.debug(f"Neither {config.daemon_name} daemon PID nor child PGIDs found.")
        return
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        if config.treat_kill_permission_error_as_not_running:
            logger.debug(f"Permission error when sending {sig.name} to {config.daemon_name} daemon. Treating as not running.")
            return
        raise
    for pgid in pgids:
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            if config.treat_kill_permission_error_as_not_running:
                logger.debug(f"Permission error when sending {sig.name} to child PGID {pgid} of {config.daemon_name} daemon. Treating as not running.")
                continue
            raise
    logger.debug(f"Requested daemon to stop with signal {sig.name}.")


class ExitedBeforeFirstLogLineError(Exception):
    pass


async def wait_until_log_line(proc: subprocess.Process, prefix: str):
    assert proc.stdout is not None
    while True:
        line_bytes = await proc.stdout.readline()
        # EOF
        if len(line_bytes) == 0:
            raise ExitedBeforeFirstLogLineError()
        line = line_bytes.decode()
        if line.startswith(prefix):
            return
        print(f"Daemon stdout> {line}", end="")


async def forward_stderr(proc: subprocess.Process):
    assert proc.stderr is not None
    while True:
        line_bytes = await proc.stderr.readline()
        # EOF
        if len(line_bytes) == 0:
            break
        line = line_bytes.decode()
        print(f"Daemon stderr> {line}", end="")


async def start_daemon(config: CtlConfig):
    python_interpreter = sys.executable
    config_json = config.to_json()
    logger.debug(f"Starting {config.daemon_name} daemon...")
    daemon_proc = await subprocess.create_subprocess_exec(
        python_interpreter, "-m", "droid_remote",
        "--config-json", config_json,
        CtlActions.FOREGROUND.cli_name,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    logger.debug(f"Waiting for {config.daemon_name} daemon to print first log line...")
    start_task = asyncio.create_task(wait_until_log_line(daemon_proc, "INFO"))
    stderr_task = asyncio.create_task(forward_stderr(daemon_proc))
    await start_task
    stderr_task.cancel()
    logger.info(f"{config.daemon_name_cap} daemon started.")


def stop_daemon(config: CtlConfig):
    logger.info(f"Stopping {config.daemon_name} daemon...")
    send_kill_signal(config, signal.SIGTERM)


async def restart_daemon(config: CtlConfig):
    logger.info(f"Restarting {config.daemon_name} daemon...")
    stop_daemon(config)
    await start_daemon(config)


def force_stop_daemon(config: CtlConfig):
    logger.info(f"Force-stopping {config.daemon_name} daemon...")
    send_kill_signal(config, signal.SIGKILL)
