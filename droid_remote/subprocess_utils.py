from asyncio import subprocess
from dataclasses import dataclass


@dataclass
class CommandException(Exception):
    command: list[str]
    returncode: int
    stderr: str
    stdout: str

    def __init__(self, command: list[str], returncode: int, stderr: str, stdout: str):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


async def run_command(*command: str) -> str:
    proc = await subprocess.create_subprocess_exec(
        *command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ret = await proc.wait()
    stdout, stderr = [s.decode() for s in await proc.communicate()]
    if ret != 0:
        raise CommandException(list(command), ret, stderr, stdout)

    return stdout
