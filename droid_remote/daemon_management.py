import logging
import asyncio
from asyncio import subprocess
import signal
import sys
import os
from .pid_management import PidFilePaths, read_pid, read_child_pgids
from .config import CtlConfig, CtlActions


logger = logging.getLogger(__name__)


def send_kill_signal(pid_file_paths: PidFilePaths, sig: signal.Signals, daemon_name: str):
    pid = read_pid(pid_file_paths.daemon_pid)
    pgids = read_child_pgids(pid_file_paths.child_pgids)
    if pid is None and len(pgids) == 0:
        logger.debug(f"Neither {daemon_name} daemon PID nor child PGIDs found.")
        return
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        pass
    for pgid in pgids:
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            pass
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


def stop_daemon(pid_file_paths: PidFilePaths, daemon_name: str):
    logger.info(f"Stopping {daemon_name} daemon...")
    send_kill_signal(pid_file_paths, signal.SIGTERM, daemon_name)


async def restart_daemon(config: CtlConfig):
    logger.info(f"Restarting {config.daemon_name} daemon...")
    stop_daemon(config.pid_file_paths, config.daemon_name)
    await start_daemon(config)


def force_stop_daemon(pid_file_paths: PidFilePaths, daemon_name: str):
    logger.info(f"Force-stopping {daemon_name} daemon...")
    send_kill_signal(pid_file_paths, signal.SIGKILL, daemon_name)
