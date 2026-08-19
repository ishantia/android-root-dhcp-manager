"""
Dynamic Network Discovery Engine for Android Tethering.
Discovers active tethering interface, gateway, subnet, and upstream route dynamically.
Author: ishantia
"""

import ipaddress
import re
from typing import Optional, List, Dict, Tuple
from dhcp_manager.core.models import NetworkState
from dhcp_manager.root.executor import RootExecutor
from dhcp_manager.logging.logger import get_logger, Subsystem


logger = get_logger(Subsystem.NETWORK)


class NetworkDiscovery:
    """Discovers active Android network interfaces, tethering subnet, gateway, and upstream."""

    def __init__(self, root_executor: RootExecutor):
        self.executor = root_executor

    def discover_state(self) -> NetworkState:
        state = NetworkState()

        # 1. Discover active tethering interface, gateway, and subnet
        tether_iface, gateway_ip, subnet_cidr = self.find_tethering_interface()
        state.tether_interface = tether_iface
        state.gateway_ip = gateway_ip
        state.subnet_cidr = subnet_cidr
        state.tethering_active = tether_iface is not None

        # 2. Discover upstream interface (e.g., tun0, rmnet0, wlan0)
        state.upstream_interface = self.find_upstream_interface(exclude_iface=tether_iface)

        return state

    def find_tethering_interface(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Scans ip route / ip addr to identify active tethering interfaces.
        Common tethering interfaces: ap0, ap1, wlan1, rndis0, usb0, bt-pan, softap0
        """
        # Command 1: ip route show
        res = self.executor.execute(["ip", "route", "show"], use_root=False)
        if not res.success:
            res = self.executor.execute(["ip", "route", "show"], use_root=True)

        if res.success:
            iface, gw, subnet = self._parse_tether_route(res.stdout)
            if iface:
                logger.info(f"Discovered tethering interface '{iface}', GW '{gw}', Subnet '{subnet}'")
                return iface, gw, subnet

        # Command 2: Fallback via ip addr show
        res_addr = self.executor.execute(["ip", "addr", "show"], use_root=False)
        if not res_addr.success:
            res_addr = self.executor.execute(["ip", "addr", "show"], use_root=True)

        if res_addr.success:
            iface, gw, subnet = self._parse_tether_addr(res_addr.stdout)
            if iface:
                logger.info(f"Discovered tethering interface via ip addr: '{iface}', GW '{gw}', Subnet '{subnet}'")
                return iface, gw, subnet

        logger.warning("No active Wi-Fi tethering interface detected.")
        return None, None, None

    def _parse_tether_route(self, route_output: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        tether_prefixes = ("ap", "softap", "wlan1", "rndis", "usb", "bt-pan", "swlan")

        for line in route_output.splitlines():
            line = line.strip()
            if not line or "default" in line:
                continue

            # Look for lines like: "10.189.149.0/24 dev ap0 proto kernel scope link src 10.189.149.185"
            parts = line.split()
            if "dev" in parts:
                dev_idx = parts.index("dev")
                if dev_idx + 1 < len(parts):
                    iface = parts[dev_idx + 1]
                    subnet_str = parts[0]

                    # Check if interface name matches known tethering pattern
                    if any(iface.startswith(p) for p in tether_prefixes) or (
                        "wlan" in iface and iface != "wlan0"
                    ) or "ap0" in iface:
                        src_ip = None
                        if "src" in parts:
                            src_idx = parts.index("src")
                            if src_idx + 1 < len(parts):
                                src_ip = parts[src_idx + 1]

                        try:
                            net = ipaddress.IPv4Network(subnet_str, strict=False)
                            gw = src_ip or str(net.network_address + 1)
                            return iface, gw, str(net)
                        except Exception:
                            pass

        return None, None, None

    def _parse_tether_addr(self, addr_output: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        current_iface = None
        tether_prefixes = ("ap", "softap", "wlan1", "rndis", "usb", "bt-pan", "swlan")

        for line in addr_output.splitlines():
            match_iface = re.match(r"^\d+:\s+([a-zA-Z0-9_\-]+):", line)
            if match_iface:
                current_iface = match_iface.group(1)
                continue

            if current_iface and "inet " in line:
                if any(current_iface.startswith(p) for p in tether_prefixes) or (
                    "wlan" in current_iface and current_iface != "wlan0"
                ):
                    match_inet = re.search(r"inet\s+([0-9\.]+)/(\d+)", line)
                    if match_inet:
                        ip_str = match_inet.group(1)
                        prefix = match_inet.group(2)
                        try:
                            net = ipaddress.IPv4Network(f"{ip_str}/{prefix}", strict=False)
                            return current_iface, ip_str, str(net)
                        except Exception:
                            pass

        return None, None, None

    def find_upstream_interface(self, exclude_iface: Optional[str] = None) -> Optional[str]:
        """
        Discovers the active default upstream route (e.g. tun0, rmnet0, wlan0).
        """
        res = self.executor.execute(["ip", "route", "show", "default"], use_root=False)
        if not res.success:
            res = self.executor.execute(["ip", "route", "show", "default"], use_root=True)

        if res.success and res.stdout:
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if "dev" in parts:
                    dev_idx = parts.index("dev")
                    if dev_idx + 1 < len(parts):
                        dev = parts[dev_idx + 1]
                        if dev != exclude_iface:
                            logger.info(f"Discovered upstream interface: '{dev}'")
                            return dev

        # Check for active tun0 (VPN) if no default route was found directly
        res_tun = self.executor.execute(["ip", "link", "show", "tun0"], use_root=False)
        if res_tun.success and "UP" in res_tun.stdout:
            return "tun0"

        return None
