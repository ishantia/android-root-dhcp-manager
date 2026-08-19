"""
Abstract Network Backend Interface.
"""

from abc import ABC, abstractmethod
import enum
from typing import List, Tuple, Optional, Dict, Any
from dhcp_manager.core.models import Assignment, DHCPLease, NetworkState
from dhcp_manager.root.executor import RootExecutor


class BackendCapability(str, enum.Enum):
    DNSMASQ_STATIC_HOSTS = "DNSMASQ_STATIC_HOSTS"
    LEASE_PARSING = "LEASE_PARSING"
    ARP_STATIC_BINDING = "ARP_STATIC_BINDING"
    SYSTEM_PROPERTY_OVERRIDE = "SYSTEM_PROPERTY_OVERRIDE"
    IPTABLES_ROUTING = "IPTABLES_ROUTING"


class NetworkBackend(ABC):
    """Abstract base class for Android DHCP and Tethering Backends."""

    def __init__(self, root_executor: RootExecutor):
        self.executor = root_executor

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the backend (e.g. 'dnsmasq', 'android_netd', 'generic_linux')."""
        pass

    @abstractmethod
    def detect_active(self) -> bool:
        """Returns True if this backend is currently active on the device."""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[BackendCapability]:
        """Returns list of capabilities supported by this backend in current environment."""
        pass

    @abstractmethod
    def parse_leases(self) -> List[DHCPLease]:
        """Parses and returns active DHCP leases."""
        pass

    @abstractmethod
    def apply_assignments(
        self,
        assignments: List[Assignment],
        network_state: NetworkState,
    ) -> Tuple[bool, List[str]]:
        """
        Applies static IP assignments to the DHCP/network server.
        Returns (success: bool, messages: list[str]).
        """
        pass

    @abstractmethod
    def verify_assignments(
        self,
        assignments: List[Assignment],
        network_state: NetworkState,
    ) -> Tuple[bool, List[str]]:
        """
        Post-apply verification to check if intended static rules are active.
        Returns (verified: bool, messages: list[str]).
        """
        pass

    @abstractmethod
    def reload_server(self) -> bool:
        """Reloads or signals the DHCP server process to pick up changes."""
        pass
