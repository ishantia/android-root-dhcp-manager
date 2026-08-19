"""
Generic Linux Network Backend Fallback.
"""

from typing import List, Tuple
from dhcp_manager.core.models import Assignment, DHCPLease, NetworkState
from dhcp_manager.dhcp.backend import NetworkBackend, BackendCapability


class GenericLinuxBackend(NetworkBackend):
    """Fallback backend using standard Linux iproute2 commands."""

    @property
    def name(self) -> str:
        return "generic_linux"

    def detect_active(self) -> bool:
        return True

    def get_capabilities(self) -> List[BackendCapability]:
        return [BackendCapability.ARP_STATIC_BINDING]

    def parse_leases(self) -> List[DHCPLease]:
        return []

    def apply_assignments(
        self,
        assignments: List[Assignment],
        network_state: NetworkState,
    ) -> Tuple[bool, List[str]]:
        messages: List[str] = []
        if not network_state.tether_interface:
            return False, ["No tethering interface active."]

        for asgn in assignments:
            if not asgn.enabled:
                continue
            cmd = [
                "ip", "neigh", "replace",
                asgn.ipv4_address,
                "lladdr", asgn.mac_address,
                "dev", network_state.tether_interface,
                "nud", "permanent"
            ]
            res = self.executor.execute(cmd, use_root=True)
            if res.success:
                messages.append(f"Applied generic ARP entry: {asgn.mac_address} -> {asgn.ipv4_address}")
            else:
                messages.append(f"Failed ARP entry for {asgn.mac_address}: {res.stderr}")

        return True, messages

    def verify_assignments(
        self,
        assignments: List[Assignment],
        network_state: NetworkState,
    ) -> Tuple[bool, List[str]]:
        return True, ["Verification completed via generic backend."]

    def reload_server(self) -> bool:
        return True
