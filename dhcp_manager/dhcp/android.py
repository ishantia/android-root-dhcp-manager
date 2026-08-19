"""
Android Tethering APEX / Netd Network Backend Implementation.
Handles modern Android tethering stacks (APEX tethering, enableLegacyDhcpServer=false, BPF tethering).
Author: ishantia
"""

from typing import List, Tuple
from dhcp_manager.core.models import Assignment, DHCPLease, NetworkState
from dhcp_manager.dhcp.backend import NetworkBackend, BackendCapability
from dhcp_manager.logging.logger import get_logger, Subsystem


logger = get_logger(Subsystem.DHCP)


class AndroidTetheringBackend(NetworkBackend):
    """Network Backend for modern Android APEX / netd tethering environments."""

    @property
    def name(self) -> str:
        return "android_netd"

    def detect_active(self) -> bool:
        # Check system properties or netd process
        res = self.executor.execute(["getprop", "sys.tethering.tethered"], use_root=False)
        if res.success and res.stdout:
            logger.info(f"Android tethering property active: {res.stdout}")
            return True

        res_ps = self.executor.execute(["ps", "-ef"], use_root=False)
        if res_ps.success and ("netd" in res_ps.stdout or "com.android.tethering" in res_ps.stdout):
            return True

        return True  # Fallback primary backend for Android systems

    def get_capabilities(self) -> List[BackendCapability]:
        return [
            BackendCapability.ARP_STATIC_BINDING,
            BackendCapability.IPTABLES_ROUTING,
        ]

    def parse_leases(self) -> List[DHCPLease]:
        # Modern Android tethering APEX stores leases in internal netd state / eBPF maps
        # Parse from ip neigh as fallback leases
        leases: List[DHCPLease] = []
        res = self.executor.execute(["ip", "neigh", "show"], use_root=False)
        if res.success and res.stdout:
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and "lladdr" in parts:
                    ip = parts[0]
                    ll_idx = parts.index("lladdr")
                    mac = parts[ll_idx + 1]
                    leases.append(
                        DHCPLease(
                            expiry_timestamp=0,
                            mac=mac,
                            ip=ip,
                            hostname="",
                        )
                    )
        return leases

    def apply_assignments(
        self,
        assignments: List[Assignment],
        network_state: NetworkState,
    ) -> Tuple[bool, List[str]]:
        messages: List[str] = []
        if not network_state.tether_interface:
            messages.append("Warning: Tethering interface is not currently active.")
            return False, messages

        messages.append(
            "Applying static IP assignments via Kernel ARP/Neighbor tables & routing rules."
        )

        for asgn in assignments:
            if not asgn.enabled:
                continue

            # Add permanent static neighbor entry
            cmd = [
                "ip", "neigh", "replace",
                asgn.ipv4_address,
                "lladdr", asgn.mac_address,
                "dev", network_state.tether_interface,
                "nud", "permanent"
            ]
            res = self.executor.execute(cmd, use_root=True)
            if res.success:
                messages.append(
                    f"Bound static ARP entry: {asgn.mac_address} -> {asgn.ipv4_address} on {network_state.tether_interface}"
                )
            else:
                messages.append(
                    f"Failed static ARP binding for {asgn.mac_address}: {res.stderr}"
                )

        return True, messages

    def verify_assignments(
        self,
        assignments: List[Assignment],
        network_state: NetworkState,
    ) -> Tuple[bool, List[str]]:
        if self.executor.dry_run:
            return True, ["[DRY-RUN] Post-apply verification simulated successfully."]

        messages: List[str] = []
        if not network_state.tether_interface:
            return False, ["Tethering interface not active."]

        res = self.executor.execute(
            ["ip", "neigh", "show", "dev", network_state.tether_interface],
            use_root=False,
        )
        if not res.success or not res.stdout:
            return False, ["Could not read ARP table."]

        all_ok = True
        for asgn in assignments:
            if not asgn.enabled:
                continue
            if asgn.ipv4_address in res.stdout and asgn.mac_address in res.stdout.lower():
                messages.append(f"VERIFIED active ARP rule: {asgn.mac_address} -> {asgn.ipv4_address}")
            else:
                all_ok = False
                messages.append(f"UNVERIFIED rule: {asgn.mac_address} -> {asgn.ipv4_address}")

        return all_ok, messages

    def reload_server(self) -> bool:
        # Netd handles ARP table dynamically
        return True
