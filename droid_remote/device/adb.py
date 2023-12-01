import asyncio
from dataclasses import dataclass
from functools import cached_property
from lxml import etree
import re
from datetime import timedelta as Timedelta

from ..subprocess_utils import run_command


# Wireless ADB timeout is 20 minutes
ADB_KEEPALIVE_INTERVAL = Timedelta(minutes=4)


async def run_adb_command(*args: str):
    return await run_command("adb", *args)


async def connect(adb_host: str):
    return await run_adb_command("connect", adb_host)


async def disconnect():
    return await run_adb_command("disconnect")


@dataclass(frozen=True)
class Device:
    connection_string: str
    connection_mode: str
    identity: dict[str, str]

    @classmethod
    def from_adb_devices_line(cls, line: str):
        connection_string, connection_mode, *identity_part_strs = line.split()
        identity_parts = [part.split(":") for part in identity_part_strs]
        identity = {key: value for key, value in identity_parts}
        return cls(connection_string, connection_mode, identity)


DEVICE_LIST_FIRST_LINE = "List of devices attached"

async def list_devices():
    devices_output = await run_adb_command("devices", "-l")
    first_line, *device_lines = devices_output.splitlines()
    if first_line != DEVICE_LIST_FIRST_LINE:
        raise ValueError(f"Unexpected output from 'adb devices': {devices_output}")
    filtered_device_lines = [line for line in device_lines if len(line) > 0]
    return [Device.from_adb_devices_line(line) for line in filtered_device_lines]


async def reboot():
    return await run_adb_command("reboot")


async def tap(coords: tuple[int, int]):
    x, y = coords
    return await run_adb_command("shell", "input", "tap", str(x), str(y))


async def read_screen_hierarchy() -> etree._Element:
    dump_output = await run_adb_command("exec-out", "uiautomator", "dump", "/dev/tty")
    hierarchy_xml_end_i = dump_output.rfind("UI hierchary dumped to: ")
    hierarchy_xml = dump_output[:hierarchy_xml_end_i]
    return etree.XML(hierarchy_xml.encode())


async def launch_app(package_name: str):
    return await run_adb_command(
        "shell",
        "monkey",
        "-p",
        package_name,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    )


async def force_stop_app(package_name: str):
    return await run_adb_command("shell", "am", "force-stop", package_name)


async def wake_up():
    return await run_adb_command("shell", "input", "keyevent", "KEYCODE_WAKEUP")


async def send_periodic_keep_alive():
    while True:
        await run_adb_command("shell", "ls")
        await asyncio.sleep(ADB_KEEPALIVE_INTERVAL.total_seconds())


@dataclass(frozen=True)
class Bounds:
    x_min: int
    y_min: int
    x_max: int
    y_max: int

    def __post_init__(self):
        if self.x_min > self.x_max:
            raise ValueError(f"x_min ({self.x_min}) > x_max ({self.x_max})")
        if self.y_min > self.y_max:
            raise ValueError(f"y_min ({self.y_min}) > y_max ({self.y_max})")

    @classmethod
    def from_coords(cls, x1: int, y1: int, x2: int, y2: int):
        x_min = min(x1, x2)
        x_max = max(x1, x2)
        y_min = min(y1, y2)
        y_max = max(y1, y2)
        return cls(x_min, y_min, x_max, y_max)

    @cached_property
    def height(self):
        return self.y_max - self.y_min

    @cached_property
    def width(self):
        return self.x_max - self.x_min

    @cached_property
    def surface_area(self):
        return self.height * self.width

    @cached_property
    def center(self):
        return ((self.x_min + self.x_max) // 2, (self.y_min + self.y_max) // 2)


def element_to_bounds(element):
    bounds = element.attrib["bounds"]
    coords = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    return Bounds.from_coords(*map(int, coords.groups()))
