from dataclasses import dataclass
from json import JSONDecodeError
import logging
from pathlib import Path
import asyncio
import os
from asyncio import subprocess
import signal
import shutil

from dataclasses_json import dataclass_json, DataClassJsonMixin

from .pid_management import save_child_pgid


NGROK_MULTIPLE_AGENTS_ERROR = "limited to 1 simultaneous ngrok agent session"
NGROK_TUNNEL_START_MESSAGE = "started tunnel"
NGROK_TUNNEL_START_TIMEOUT = 10
logger = logging.getLogger(__name__)


@dataclass_json
@dataclass
class NgrokLogMessage(DataClassJsonMixin):
    lvl: str
    msg: str
    t: str


async def wait_until_ngrok_tunnel_starts(proc: subprocess.Process):
    assert proc.stdout is not None
    while True:
        line_bytes = await proc.stdout.readline()
        if len(line_bytes) == 0:
            return
        json_line = line_bytes.decode()
        try:
            message = NgrokLogMessage.from_json(json_line)
        except JSONDecodeError:
            continue
        if message.lvl == "info" and message.msg.lower() == NGROK_TUNNEL_START_MESSAGE:
            return


async def run_ngrok(domain: str, child_pgids_file_path: Path):
    logger.info(f"Starting ngrok for domain {domain}...")
    ngrok_command = [
        "http",
        f"--domain={domain}",
        "8080",
        "--log=stdout",
        "--log-format=json",
    ]
    ngrok_command_path = shutil.which("ngrok")
    if ngrok_command_path is None:
        raise Exception("Could not find ngrok command.")
    # Run ngrok through bash because the shebang line in the startup script on
    # Termux is wrong. Also: https://github.com/termux/termux-tasker#termux-environment.
    shell_interpreter_path = shutil.which("bash")
    if shell_interpreter_path is None:
        shell_interpreter_path = shutil.which("sh")
    if shell_interpreter_path is None:
        raise Exception("Could find neither 'bash' nor 'sh'.")
    ngrok_process = await asyncio.create_subprocess_exec(
        shell_interpreter_path,
        ngrok_command_path,
        *ngrok_command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    pid = ngrok_process.pid
    pgid = os.getpgid(pid)
    logger.info(f"Started ngrok ({pgid=}). Establishing tunnel...")
    save_child_pgid(child_pgids_file_path, pgid)
    try:
        async with asyncio.timeout(NGROK_TUNNEL_START_TIMEOUT):
            await wait_until_ngrok_tunnel_starts(ngrok_process)
    except asyncio.TimeoutError:
        logger.error(
            f"ngrok did not start a tunnel within {NGROK_TUNNEL_START_TIMEOUT} seconds."
        )
        raise
    logger.info("ngrok started a tunnel.")
    try:
        return_code = await ngrok_process.wait()
    except asyncio.CancelledError:
        logger.info("Terminating ngrok process tree...")
        os.killpg(pgid, signal.SIGTERM)
        try:
            async with asyncio.timeout(3):
                return_code = await ngrok_process.wait()
            logger.info(f"ngrok exited cleanly ({return_code=}).")
        except asyncio.TimeoutError:
            logger.info("ngrok did not respond to SIGTERM. Sending SIGKILL...")
            os.killpg(pgid, signal.SIGKILL)
            return_code = await ngrok_process.wait()
            logger.info(f"ngrok exited after SIGKILL ({return_code=}).")
        raise
    stderr_stream = ngrok_process.stderr
    assert stderr_stream is not None
    stderr = (await stderr_stream.read()).decode()
    if return_code == 1 and NGROK_MULTIPLE_AGENTS_ERROR in stderr:
        raise Exception("Another ngrok agent is already running.")
    if return_code != 0:
        logger.error(f"ngrok exited with non-zero return code {return_code}")
        logger.error(f"ngrok stderr: \n{stderr}\n")
        raise Exception(f"ngrok exited with non-zero return code {return_code}")

    logger.info("ngrok exited cleanly.")
