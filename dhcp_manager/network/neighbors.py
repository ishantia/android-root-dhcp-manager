"""
Neighbor and ARP table scanner module.
Parses active connected clients from 'ip neigh' and '/proc/net/arp'.
Author: ishantia
"""

import time
from typing import List, Optional
from dhcp_manager.core.models import NeighborEntry
from dhcp_manager.core.validator import is_valid_mac, is_valid_ipv4, normalize_mac, normalize_ipv4
from dhcp_manager.root.executor import RootExecutor
from dhcp_manager.logging.logger import get_logger, Subsystem


logger = get_logger(Subsystem.CLIENT)


class NeighborScanner:
    """Discovers connected client devices on local network interfaces via ARP / ip neigh."""

    def __init__(self, root_executor: RootExecutor):
        self.executor = root_executor

    def get_connected_clients(self, target_interface: Optional[str] = None) -> List[NeighborEntry]:
        clients: List[NeighborEntry] = []

        # Strategy 1: ip neigh show
        ip_neigh_clients = self._scan_ip_neigh(target_interface)
        if ip_neigh_clients:
            clients.extend(ip_neigh_clients)

        # Strategy 2: /proc/net/arp fallback/supplement
        arp_clients = self._scan_proc_net_arp(target_interface)
        existing_ips = {c.ip for c in clients}

        for ac in arp_clients:
            if ac.ip not in existing_ips:
                clients.append(ac)

        logger.debug(f"Discovered {len(clients)} neighbor entries.")
        return clients

    def _scan_ip_neigh(self, target_interface: Optional[str]) -> List[NeighborEntry]:
        cmd = ["ip", "neigh", "show"]
        if target_interface:
            cmd.extend(["dev", target_interface])

        res = self.executor.execute(cmd, use_root=False)
        if not res.success:
            res = self.executor.execute(cmd, use_root=True)

        if not res.success or not res.stdout:
            return []

        entries: List[NeighborEntry] = []
        now = time.time()

        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) < 3:
                continue

            ip = parts[0]
            if not is_valid_ipv4(ip):
                continue

            dev = ""
            mac = ""
            state = parts[-1] if parts else "UNKNOWN"
            is_router = "router" in parts

            if "dev" in parts:
                dev_idx = parts.index("dev")
                if dev_idx + 1 < len(parts):
                    dev = parts[dev_idx + 1]

            if "lladdr" in parts:
                ll_idx = parts.index("lladdr")
                if ll_idx + 1 < len(parts):
                    mac = parts[ll_idx + 1]

            if mac and is_valid_mac(mac):
                norm_mac = normalize_mac(mac)
                norm_ip = normalize_ipv4(ip)
                entries.append(
                    NeighborEntry(
                        ip=norm_ip,
                        mac=norm_mac,
                        interface=dev,
                        state=state,
                        is_router=is_router,
                        last_updated=now,
                    )
                )

        return entries

    def _scan_proc_net_arp(self, target_interface: Optional[str]) -> List[NeighborEntry]:
        res = self.executor.execute(["cat", "/proc/net/arp"], use_root=False)
        if not res.success or not res.stdout:
            return []

        entries: List[NeighborEntry] = []
        now = time.time()
        lines = res.stdout.splitlines()

        # Line 0 is header: IP address HW type Flags HW address Mask Device
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) < 6:
                continue

            ip = parts[0]
            mac = parts[3]
            dev = parts[5]

            if target_interface and dev != target_interface:
                continue

            if is_valid_ipv4(ip) and is_valid_mac(mac) and mac != "00:00:00:00:00:00":
                entries.append(
                    NeighborEntry(
                        ip=normalize_ipv4(ip),
                        mac=normalize_mac(mac),
                        interface=dev,
                        state="ARP",
                        last_updated=now,
                    )
                )

        return entries
