"""
IP & MAC Conflict Detection Engine.
Inspects stored assignments, active neighbor tables, DHCP leases, and subnet configuration.
"""

from typing import List, Optional
from dhcp_manager.core.models import (
    Assignment,
    ConflictWarning,
    ConflictSeverity,
    NetworkState,
    NeighborEntry,
    DHCPLease,
)
from dhcp_manager.core.validator import (
    normalize_mac,
    normalize_ipv4,
    is_valid_mac,
    is_valid_ipv4,
    validate_subnet,
    is_reserved_or_special_ip,
)


class ConflictDetector:
    """Detects IP address and MAC collisions before applying DHCP assignments."""

    def __init__(
        self,
        existing_assignments: List[Assignment],
        network_state: Optional[NetworkState] = None,
    ):
        self.existing_assignments = existing_assignments
        self.network_state = network_state or NetworkState()

    def check_assignment(
        self,
        mac: str,
        ip: str,
        ignore_assignment_id: Optional[int] = None,
    ) -> List[ConflictWarning]:
        conflicts: List[ConflictWarning] = []

        # 1. Validate MAC format
        try:
            norm_mac = normalize_mac(mac)
        except ValueError as e:
            conflicts.append(
                ConflictWarning(
                    severity=ConflictSeverity.ERROR,
                    code="INVALID_MAC",
                    message=str(e),
                    target_mac=mac,
                    target_ip=ip,
                )
            )
            return conflicts

        # 2. Validate IPv4 format
        try:
            norm_ip = normalize_ipv4(ip)
        except ValueError as e:
            conflicts.append(
                ConflictWarning(
                    severity=ConflictSeverity.ERROR,
                    code="INVALID_IP",
                    message=str(e),
                    target_mac=norm_mac,
                    target_ip=ip,
                )
            )
            return conflicts

        # 3. Check subnet bounds if subnet is known
        subnet = self.network_state.subnet_cidr
        if subnet and not validate_subnet(norm_ip, subnet):
            conflicts.append(
                ConflictWarning(
                    severity=ConflictSeverity.ERROR,
                    code="OUT_OF_SUBNET",
                    message=f"IPv4 address '{norm_ip}' is outside active tethering subnet '{subnet}'.",
                    target_mac=norm_mac,
                    target_ip=norm_ip,
                )
            )

        # 4. Check Gateway Collision
        gw = self.network_state.gateway_ip
        if gw and norm_ip == gw:
            conflicts.append(
                ConflictWarning(
                    severity=ConflictSeverity.ERROR,
                    code="GATEWAY_COLLISION",
                    message=f"IPv4 address '{norm_ip}' is the tethering gateway IP.",
                    target_mac=norm_mac,
                    target_ip=norm_ip,
                )
            )

        # 5. Check Reserved / Network / Broadcast IP
        if is_reserved_or_special_ip(norm_ip, subnet):
            conflicts.append(
                ConflictWarning(
                    severity=ConflictSeverity.ERROR,
                    code="RESERVED_IP",
                    message=f"IPv4 address '{norm_ip}' is a reserved, network, or broadcast address.",
                    target_mac=norm_mac,
                    target_ip=norm_ip,
                )
            )

        # 6. Check Database IP Assignment Collisions
        for asgn in self.existing_assignments:
            if ignore_assignment_id is not None and asgn.id == ignore_assignment_id:
                continue

            asgn_mac = normalize_mac(asgn.mac_address)
            asgn_ip = normalize_ipv4(asgn.ipv4_address)

            if asgn_ip == norm_ip and asgn_mac != norm_mac:
                conflicts.append(
                    ConflictWarning(
                        severity=ConflictSeverity.ERROR,
                        code="DB_IP_COLLISION",
                        message=(
                            f"IPv4 address '{norm_ip}' is already assigned to client "
                            f"'{asgn_mac}' ({asgn.hostname or 'unnamed'})."
                        ),
                        target_mac=norm_mac,
                        target_ip=norm_ip,
                        details={"conflicting_mac": asgn_mac, "hostname": asgn.hostname},
                    )
                )

            if asgn_mac == norm_mac and asgn_ip != norm_ip:
                conflicts.append(
                    ConflictWarning(
                        severity=ConflictSeverity.WARNING,
                        code="DB_MAC_REASSIGNED",
                        message=(
                            f"MAC address '{norm_mac}' already has stored IP assignment '{asgn_ip}'. "
                            f"Saving will update this assignment to '{norm_ip}'."
                        ),
                        target_mac=norm_mac,
                        target_ip=norm_ip,
                        details={"old_ip": asgn_ip},
                    )
                )

        # 7. Check Active Connected Neighbors (ARP / ip neigh)
        for client in self.network_state.connected_clients:
            if not client.mac:
                continue

            try:
                c_mac = normalize_mac(client.mac)
                c_ip = normalize_ipv4(client.ip)
            except ValueError:
                continue

            if c_ip == norm_ip and c_mac != norm_mac:
                conflicts.append(
                    ConflictWarning(
                        severity=ConflictSeverity.WARNING,
                        code="ACTIVE_IP_IN_USE",
                        message=(
                            f"IPv4 address '{norm_ip}' is currently in use on the network "
                            f"by device '{c_mac}' (state: {client.state})."
                        ),
                        target_mac=norm_mac,
                        target_ip=norm_ip,
                        details={"active_mac": c_mac, "state": client.state},
                    )
                )

        # 8. Check DHCP Active Leases
        for lease in self.network_state.dhcp_leases:
            try:
                l_mac = normalize_mac(lease.mac)
                l_ip = normalize_ipv4(lease.ip)
            except ValueError:
                continue

            if l_ip == norm_ip and l_mac != norm_mac:
                conflicts.append(
                    ConflictWarning(
                        severity=ConflictSeverity.WARNING,
                        code="DHCP_LEASE_COLLISION",
                        message=(
                            f"IPv4 address '{norm_ip}' is currently leased by DHCP server "
                            f"to MAC '{l_mac}'."
                        ),
                        target_mac=norm_mac,
                        target_ip=norm_ip,
                        details={"leased_mac": l_mac},
                    )
                )

        return conflicts
