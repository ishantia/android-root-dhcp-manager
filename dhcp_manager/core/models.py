"""
Core Data Models for Android Root DHCP Manager.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import enum
from typing import Optional, Any, Dict, List


@dataclass
class Assignment:
    mac_address: str
    ipv4_address: str
    hostname: str = ""
    enabled: bool = True
    notes: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_seen_at: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Assignment":
        return cls(
            id=data.get("id"),
            mac_address=data["mac_address"],
            ipv4_address=data["ipv4_address"],
            hostname=data.get("hostname", ""),
            enabled=bool(data.get("enabled", True)),
            notes=data.get("notes", ""),
            created_at=data.get("created_at")
            or datetime.now(timezone.utc).isoformat(),
            updated_at=data.get("updated_at")
            or datetime.now(timezone.utc).isoformat(),
            last_seen_at=data.get("last_seen_at"),
        )


@dataclass
class NeighborEntry:
    ip: str
    mac: str
    interface: str
    state: str = "UNKNOWN"
    is_router: bool = False
    hostname: Optional[str] = None
    last_updated: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DHCPLease:
    expiry_timestamp: int
    mac: str
    ip: str
    hostname: str = ""
    client_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConflictSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class ConflictWarning:
    severity: ConflictSeverity
    code: str
    message: str
    target_mac: str
    target_ip: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NetworkState:
    tethering_active: bool = False
    tether_interface: Optional[str] = None
    gateway_ip: Optional[str] = None
    subnet_cidr: Optional[str] = None
    upstream_interface: Optional[str] = None
    dhcp_backend_type: str = "unknown"
    dnsmasq_pid: Optional[int] = None
    dnsmasq_cmd: Optional[str] = None
    dnsmasq_lease_file: Optional[str] = None
    connected_clients: List[NeighborEntry] = field(default_factory=list)
    dhcp_leases: List[DHCPLease] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tethering_active": self.tethering_active,
            "tether_interface": self.tether_interface,
            "gateway_ip": self.gateway_ip,
            "subnet_cidr": self.subnet_cidr,
            "upstream_interface": self.upstream_interface,
            "dhcp_backend_type": self.dhcp_backend_type,
            "dnsmasq_pid": self.dnsmasq_pid,
            "dnsmasq_cmd": self.dnsmasq_cmd,
            "dnsmasq_lease_file": self.dnsmasq_lease_file,
            "connected_clients_count": len(self.connected_clients),
            "dhcp_leases_count": len(self.dhcp_leases),
        }
