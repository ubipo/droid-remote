import logging
import urllib.request
from .pid_management import PidFilePaths, read_pid, check_if_process_running


logger = logging.getLogger(__name__)


class DaemonHealthCheckError(Exception):
    pass


def check_daemon_health_http(base_url: str):
    try:
        url = f"{base_url}/metrics"
        with urllib.request.urlopen(base_url + "/metrics", timeout=1) as resp:
            status_range = resp.status // 100
            if status_range != 2:
                logger.warning(f"Daemon health check failed: HTTP GET to '{url}' returned status code {resp.status} ({status_range=})")
                raise DaemonHealthCheckError(
                    f"/metrics HTTP endpoint returned status code {resp.status}"
                )
            return True
    except urllib.error.URLError as e:
        if isinstance(e.reason, ConnectionRefusedError):
            logger.debug("Daemon health check failed: Connection refused")
            return False
        logger.warning(f"Unexpected URLError while checking daemon health: {e}")
        raise DaemonHealthCheckError(e)
    except Exception as e:
        logger.warning(f"Unexpected error while checking daemon health: {e.__class__.__name__}: {e}")
        raise DaemonHealthCheckError(e)


def check_if_daemon_healthy(pid_file_paths: PidFilePaths, base_url: str):
    pid = read_pid(pid_file_paths.daemon_pid)
    process_healthy = check_if_process_running(pid)
    http_healthy = check_daemon_health_http(base_url)
    return process_healthy and http_healthy


def safe_check_if_daemon_healthy(pid_file_paths: PidFilePaths, base_url: str):
    try:
        return check_if_daemon_healthy(pid_file_paths, base_url)
    except DaemonHealthCheckError:
        return False
