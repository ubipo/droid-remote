from dataclasses import dataclass


@dataclass
class UnknownTaskException(Exception):
    task_name: str


@dataclass
class TaskExecutionException(Exception):
    return_code: int
    result: str


@dataclass
class TaskTimeoutException(Exception):
    correlation_id: str
    task_name: str
    timeout: float
