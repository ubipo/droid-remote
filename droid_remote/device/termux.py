import json
import asyncio
from dataclasses import dataclass
from ..subprocess_utils import run_command, CommandException


async def wake_lock():
    return await run_command("termux-wake-lock")


async def wake_unlock():
    return await run_command("termux-wake-unlock")


async def set_screen_brightness(brightness: int):
    if brightness < 0 or brightness > 255:
        raise ValueError("Brightness must be between 0 and 255")
    return await run_command("termux-brightness", str(brightness))


async def query_battery_status():
    battery_status_json = await run_command("termux-battery-status")
    return json.loads(battery_status_json)


async def start_activity(package_name: str, activity_name: str):
    try:
        return await run_command("am", "start", "-n", f"{package_name}/{activity_name}")
    except CommandException as e:
        if e.returncode == 1 and "InvocationTargetException" in e.stderr:
            # Always happens, but action still succeeds
            pass
        else:
            raise


async def start_tasker():
    return await start_activity("net.dinglisch.android.taskerm", ".Tasker")


async def start_tailscale_vpnservice():
    await start_activity("com.tailscale.ipn", ".IPNActivity")
    await asyncio.sleep(1)
    await run_command("am", "broadcast", "--user", "0", "-a", "com.tailscale.ipn.CONNECT_VPN", "-n", "com.tailscale.ipn/.IPNReceiver")
    return "Started Tailscale VPN"


@dataclass(frozen=True)
class NoVpnInterface:
    pass


@dataclass(frozen=True)
class VpnInterface:
    name: str
    ip_addresses: list[str]


def get_vpn_interface():
    import netifaces
    families = [netifaces.AF_INET, netifaces.AF_INET6]
    interfaces = netifaces.interfaces()
    vpn_interfaces = [interface for interface in interfaces if interface.startswith("tun")]
    if len(vpn_interfaces) == 0:
        return NoVpnInterface()
    elif len(vpn_interfaces) > 1:
        raise ValueError(f"More than one VPN interface found: {vpn_interfaces}")
    
    interface = vpn_interfaces[0]
    addresses = [
        address for family in families
        for address in netifaces.ifaddresses(interface).get(family, [])
    ]
    return VpnInterface(
        name=interface,
        ip_addresses=list([address.get("addr") for address in addresses]),
    )


async def go_home():
    try:
        await run_command(
            "am",
            "start",
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.HOME",
        )
    except CommandException as e:
        if e.returncode == 1 and "InvocationTargetException" in e.stderr:
            # Always happens, but action still succeeds
            pass
        else:
            raise


@dataclass(frozen=True)
class IdleInfo:
    screen_on: bool
    locked: bool
    charging: bool
    moving: bool


def get_idle_info_item(lines: list[str], name: str) -> bool:
    for line in lines:
        if line.strip().startswith(name):
            (_, value) = line.split("=", 1)
            return value.strip().lower() == "true"
    raise ValueError(f"Could not find {name} in idle info")


async def query_idle_info():
    raw = await run_command("/system/bin/dumpsys", "deviceidle")
    lines = raw.splitlines()
    return IdleInfo(
        screen_on=get_idle_info_item(lines, "mScreenOn"),
        locked=get_idle_info_item(lines, "mScreenLocked"),
        charging=get_idle_info_item(lines, "mCharging"),
        moving=not get_idle_info_item(lines, "mNotMoving"),
    )
