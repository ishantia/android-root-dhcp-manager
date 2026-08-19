"""
DHCP and Network Backend Abstraction package.
"""

from dhcp_manager.dhcp.backend import NetworkBackend, BackendCapability
from dhcp_manager.dhcp.dnsmasq import DnsmasqBackend
from dhcp_manager.dhcp.android import AndroidTetheringBackend
from dhcp_manager.dhcp.generic import GenericLinuxBackend

__all__ = [
    "NetworkBackend",
    "BackendCapability",
    "DnsmasqBackend",
    "AndroidTetheringBackend",
    "GenericLinuxBackend",
]
