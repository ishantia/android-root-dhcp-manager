"""
Dnsmasq Network Backend Implementation.
Handles dnsmasq process detection, lease file parsing, static host injection, and reload signals.
Author: ishantia
"""

import os
import re
from typing import List, Tuple, Optional, Dict
from dhcp_manager.core.models import Assignment, DHCPLease, NetworkState
from dhcp_manager.core.validator import normalize_mac, normalize_ipv4, is_valid_mac, is_valid_ipv4
from dhcp_manager.dhcp.backend import NetworkBackend, BackendCapability
from dhcp_manager.logging.logger import get_logger, Subsystem


logger = get_logger(Subsystem.DNSMASQ)

DEFAULT_LEASE_FILES = [
    "/data/misc/dhcp/dnsmasq.leases",
    "/data/vendor/dhcp/dnsmasq.leases",
    "/data/system/dhcp/dnsmasq.leases",
    "/var/lib/misc/dnsmasq.leases",
]

DEFAULT_HOSTS_FILES = [
    "/data/misc/dhcp/dnsmasq.hosts",
    "/data/vendor/dhcp/dnsmasq.hosts",
    "/data/misc/dhcp/hosts",
]

DEFAULT_CONF_DIRS = [
    "/data/misc/dhcp/dnsmasq.d",
    "/data/vendor/dhcp/dnsmasq.d",
]


class DnsmasqBackend(NetworkBackend):
    """Network Backend for devices running dnsmasq for Wi-Fi hotspot DHCP."""

    def __init__(self, root_executor):
        super().__init__(root_executor)
        self.pid: Optional[int] = None
        self.cmdline: Optional[str] = None
        self.lease_file: Optional[str] = None
        self.hosts_file: Optional[str] = None
        self.conf_dir: Optional[str] = None

    @property
    def name(self) -> str:
        return "dnsmasq"

    def detect_active(self) -> bool:
        # Check ps for dnsmasq
        res = self.executor.execute(["ps", "-ef"], use_root=False)
        if not res.success:
            res = self.executor.execute(["ps", "aux"], use_root=False)
        if not res.success:
            res = self.executor.execute(["ps"], use_root=True)

        if res.success and res.stdout:
            for line in res.stdout.splitlines():
                if "dnsmasq" in line and not "grep" in line and "dhcp_manager" not in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        try:
                            # Usually PID is column 1 (ps -ef/aux)
                            pid_candidate = int(parts[1]) if parts[1].isdigit() else int(parts[0])
                            self.pid = pid_candidate
                            self.cmdline = line
                            self._extract_paths_from_cmdline(line)
                            logger.info(f"Detected active dnsmasq process PID {self.pid}")
                            return True
                        except ValueError:
                            pass

        # Fallback check lease file existence
        for lf in DEFAULT_LEASE_FILES:
            chk = self.executor.execute(["test", "-f", lf], use_root=True)
            if chk.success:
                self.lease_file = lf
                logger.info(f"Detected dnsmasq lease file: {lf}")
                return True

        return False

    def _extract_paths_from_cmdline(self, cmd: str) -> None:
        match_lease = re.search(r"--dhcp-leasefile=([^\s]+)", cmd)
        if match_lease:
            self.lease_file = match_lease.group(1)

        match_hosts = re.search(r"--addn-hosts=([^\s]+)|--dhcp-hostsfile=([^\s]+)", cmd)
        if match_hosts:
            self.hosts_file = match_hosts.group(1) or match_hosts.group(2)

        match_dir = re.search(r"--conf-dir=([^\s,]+)", cmd)
        if match_dir:
            self.conf_dir = match_dir.group(1)

    def get_capabilities(self) -> List[BackendCapability]:
        caps = [BackendCapability.LEASE_PARSING]
        if self.pid or self.hosts_file or self.conf_dir:
            caps.append(BackendCapability.DNSMASQ_STATIC_HOSTS)
        return caps

    def parse_leases(self) -> List[DHCPLease]:
        target_file = self.lease_file or self._find_existing_lease_file()
        if not target_file:
            return []

        res = self.executor.execute(["cat", target_file], use_root=True)
        if not res.success or not res.stdout:
            return []

        leases: List[DHCPLease] = []
        # Lease line format: <expiry_timestamp> <mac> <ip> <hostname> <client_id>
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3:
                try:
                    exp = int(parts[0])
                    mac = parts[1]
                    ip = parts[2]
                    hostname = parts[3] if len(parts) > 3 and parts[3] != "*" else ""
                    client_id = parts[4] if len(parts) > 4 else ""

                    if is_valid_mac(mac) and is_valid_ipv4(ip):
                        leases.append(
                            DHCPLease(
                                expiry_timestamp=exp,
                                mac=normalize_mac(mac),
                                ip=normalize_ipv4(ip),
                                hostname=hostname,
                                client_id=client_id,
                            )
                        )
                except (ValueError, IndexError):
                    continue

        return leases

    def _find_existing_lease_file(self) -> Optional[str]:
        for path in DEFAULT_LEASE_FILES:
            chk = self.executor.execute(["test", "-f", path], use_root=True)
            if chk.success:
                return path
        return None

    def apply_assignments(
        self,
        assignments: List[Assignment],
        network_state: NetworkState,
    ) -> Tuple[bool, List[str]]:
        messages: List[str] = []
        enabled_assignments = [a for a in assignments if a.enabled]

        if not enabled_assignments:
            messages.append("No enabled static assignments to apply.")
            return True, messages

        # Option A: Write dnsmasq config fragment dhcp-host if conf_dir exists
        target_conf_dir = self.conf_dir or self._find_existing_conf_dir()
        if target_conf_dir:
            success, msg = self._write_dnsmasq_conf(target_conf_dir, enabled_assignments)
            messages.append(msg)
            if success:
                self.reload_server()
                return True, messages

        # Option B: Write to hosts file
        target_hosts = self.hosts_file or self._find_or_create_hosts_file()
        if target_hosts:
            success, msg = self._write_dnsmasq_hosts(target_hosts, enabled_assignments)
            messages.append(msg)
            if success:
                self.reload_server()
                return True, messages

        # Option C: Direct ARP neighbor injection as backup
        messages.append("Applying static assignments via ARP neighbor injection.")
        for asgn in enabled_assignments:
            if network_state.tether_interface:
                cmd = [
                    "ip", "neigh", "replace",
                    asgn.ipv4_address,
                    "lladdr", asgn.mac_address,
                    "dev", network_state.tether_interface,
                    "nud", "permanent"
                ]
                res = self.executor.execute(cmd, use_root=True)
                if res.success:
                    messages.append(f"Bound ARP {asgn.mac_address} -> {asgn.ipv4_address}")
                else:
                    messages.append(f"Failed ARP bound for {asgn.mac_address}: {res.stderr}")

        return True, messages

    def _find_existing_conf_dir(self) -> Optional[str]:
        for path in DEFAULT_CONF_DIRS:
            chk = self.executor.execute(["test", "-d", path], use_root=True)
            if chk.success:
                return path
        return None

    def _find_or_create_hosts_file(self) -> str:
        for path in DEFAULT_HOSTS_FILES:
            chk = self.executor.execute(["test", "-f", path], use_root=True)
            if chk.success:
                return path
        # Default fallback
        return DEFAULT_HOSTS_FILES[0]

    def _write_dnsmasq_conf(self, conf_dir: str, assignments: List[Assignment]) -> Tuple[bool, str]:
        conf_file = f"{conf_dir}/01-dhcp-manager.conf"
        lines = [
            "# Generated by Android Root DHCP Manager",
            "# DO NOT EDIT MANUALLY",
        ]
        for a in assignments:
            host_str = f",{a.hostname}" if a.hostname else ""
            lines.append(f"dhcp-host={a.mac_address},{a.ipv4_address}{host_str}")

        content = "\n".join(lines) + "\n"
        # Write via root executor echo/cat
        cmd = f"cat << 'EOF' > {conf_file}\n{content}EOF"
        res = self.executor.execute(cmd, use_root=True)
        if res.success:
            return True, f"Wrote static leases to {conf_file}"
        return False, f"Failed writing {conf_file}: {res.stderr}"

    def _write_dnsmasq_hosts(self, hosts_file: str, assignments: List[Assignment]) -> Tuple[bool, str]:
        lines = ["# Android Root DHCP Manager Static Hosts"]
        for a in assignments:
            host = a.hostname or f"device-{a.mac_address.replace(':', '')}"
            lines.append(f"{a.ipv4_address}\t{host}")

        content = "\n".join(lines) + "\n"
        cmd = f"cat << 'EOF' > {hosts_file}\n{content}EOF"
        res = self.executor.execute(cmd, use_root=True)
        if res.success:
            return True, f"Wrote static hosts to {hosts_file}"
        return False, f"Failed writing {hosts_file}: {res.stderr}"

    def reload_server(self) -> bool:
        if self.pid:
            res = self.executor.execute(["kill", "-HUP", str(self.pid)], use_root=True)
            if res.success:
                logger.info(f"Sent SIGHUP to dnsmasq PID {self.pid}")
                return True

        # Try killall dnsmasq HUP
        res = self.executor.execute(["killall", "-HUP", "dnsmasq"], use_root=True)
        return res.success

    def verify_assignments(
        self,
        assignments: List[Assignment],
        network_state: NetworkState,
    ) -> Tuple[bool, List[str]]:
        if self.executor.dry_run:
            return True, ["[DRY-RUN] Post-apply verification simulated successfully."]

        messages: List[str] = []
        enabled = [a for a in assignments if a.enabled]
        if not enabled:
            return True, ["No enabled assignments to verify."]

        # Check if dnsmasq hosts or conf file contains the assignments
        all_ok = True
        target_conf = self.conf_dir or self._find_existing_conf_dir()
        if target_conf:
            conf_file = f"{target_conf}/01-dhcp-manager.conf"
            res = self.executor.execute(["cat", conf_file], use_root=True)
            if res.success and res.stdout:
                for a in enabled:
                    if a.mac_address in res.stdout and a.ipv4_address in res.stdout:
                        messages.append(f"VERIFIED in {conf_file}: {a.mac_address} -> {a.ipv4_address}")
                    else:
                        all_ok = False
                        messages.append(f"MISSING in {conf_file}: {a.mac_address} -> {a.ipv4_address}")

        return all_ok, messages
