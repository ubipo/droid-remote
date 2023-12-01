from dataclasses import dataclass
import os
import sys
from typing import Callable, Optional
from pathlib import Path


@dataclass(frozen=True)
class PidFilePaths:
    daemon_pid: Path
    child_pgids: Optional[Path] = None


@dataclass(frozen=True)
class DaemonStillRunning:
    pid: int


@dataclass(frozen=True)
class ChildProcessStillRunning:
    pgid: int


def read_pid(pid_file_path: Path):
    try:
        return int(pid_file_path.read_text())
    except FileNotFoundError:
        return None


def read_child_pgids(child_pgids_file_path: Optional[Path]) -> list[int]:
    if child_pgids_file_path is None:
        return []
    try:
        return [int(line) for line in child_pgids_file_path.read_text().splitlines()]
    except FileNotFoundError:
        return []


def check_if_process_running(
    pid: Optional[int],
    treat_kill_permission_error_as_not_running: bool = False,
    send_signal: Optional[Callable] = None,
):
    if pid is None:
        return False
    if send_signal is None:
        def send_signal():
            os.kill(pid, 0)
    try:
        send_signal()
    except ProcessLookupError:
        return False
    except PermissionError:
        if treat_kill_permission_error_as_not_running:
            return False
        raise
    return True


def check_if_process_group_running(
    pgid: int,
    treat_kill_permission_error_as_not_running: bool = False,
):
    return check_if_process_running(
        None,
        treat_kill_permission_error_as_not_running,
        lambda: os.killpg(pgid, 0)
    )


def ensure_no_existing_process_or_exit(
    pid_file_paths: PidFilePaths,
    daemon_name: str,
    treat_kill_permission_error_as_not_running: bool = False
):
    daemon_name_cap = daemon_name.capitalize()
    pid = read_pid(pid_file_paths.daemon_pid)
    if pid is not None:
        if check_if_process_running(pid, treat_kill_permission_error_as_not_running):
            print(f"{daemon_name_cap} is still/already running ({pid=}).", file=sys.stderr)
            sys.exit(1)
    child_pgids = read_child_pgids(pid_file_paths.child_pgids)
    for pgid in child_pgids:
        if check_if_process_group_running(pgid, treat_kill_permission_error_as_not_running):
            print(
                f"Stray child processes of existing {daemon_name} instance are still running ({pgid=}).",
                file=sys.stderr,
            )
            sys.exit(1)


def init_pid_files(pid_file_paths: PidFilePaths):
    my_pid = os.getpid()
    pid_file_paths.daemon_pid.write_text(str(my_pid))
    if pid_file_paths.child_pgids is not None:
        pid_file_paths.child_pgids.write_text("")


def save_child_pgid(child_pgids_file_path: Path, pgid: int):
    pgids = set(
        (
            *read_child_pgids(child_pgids_file_path),
            pgid,
        )
    )
    child_pgids_file_path.write_text("\n".join(str(pgid) for pgid in pgids))


def clear_pid_files(pid_file_paths: PidFilePaths):
    pid_file_paths.daemon_pid.unlink(missing_ok=True)
    if pid_file_paths.child_pgids is not None:
        pid_file_paths.child_pgids.unlink(missing_ok=True)
