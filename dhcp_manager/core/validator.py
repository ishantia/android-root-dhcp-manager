"""
Validation utilities for MAC addresses, IPv4 addresses, subnets, and hostnames.
Author: ishantia
"""

import ipaddress
import re
from typing import Optional


MAC_REGEX = re.compile(r"^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$")
MAC_NO_DELIM_REGEX = re.compile(r"^[0-9a-fA-F]{12}$")
HOSTNAME_REGEX = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")


def normalize_mac(mac: str) -> str:
    """
    Normalizes any valid MAC address format into standard colon-separated lowercase:
    e.g., '28-3F-69-64-69-73' -> '28:3f:69:64:69:73'
    '283F69646973' -> '28:3f:69:64:69:73'
    """
    if not mac or not isinstance(mac, str):
        raise ValueError("MAC address must be a non-empty string.")

    cleaned = mac.strip()

    if MAC_REGEX.match(cleaned):
        octets = cleaned.replace("-", ":").lower().split(":")
        return ":".join(octets)

    # Handle cisco dot format e.g. 283f.6964.6973
    dot_cleaned = cleaned.replace(".", "")
    if MAC_NO_DELIM_REGEX.match(dot_cleaned):
        hex_str = dot_cleaned.lower()
        octets = [hex_str[i : i + 2] for i in range(0, 12, 2)]
        return ":".join(octets)

    raise ValueError(f"Invalid MAC address format: '{mac}'")


def is_valid_mac(mac: str) -> bool:
    """Returns True if string is a valid MAC address, False otherwise."""
    try:
        normalize_mac(mac)
        return True
    except ValueError:
        return False


def is_private_mac(mac: str) -> bool:
    """
    Checks if a MAC address has the Locally Administered (randomized/private) bit set.
    The second character of the first octet will be 2, 6, A, or E.
    """
    norm = normalize_mac(mac)
    first_octet_second_char = norm[1]
    return first_octet_second_char in ("2", "6", "a", "e")


def normalize_ipv4(ip: str) -> str:
    """
    Validates and normalizes an IPv4 address string (stripping leading zeros in octets).
    Raises ValueError if invalid.
    """
    if not ip or not isinstance(ip, str):
        raise ValueError("IPv4 address must be a non-empty string.")
    cleaned = ip.strip()
    try:
        obj = ipaddress.IPv4Address(cleaned)
        return str(obj)
    except Exception as e:
        raise ValueError(f"Invalid IPv4 address '{ip}': {e}")


def is_valid_ipv4(ip: str) -> bool:
    """Returns True if string is a valid IPv4 address, False otherwise."""
    try:
        normalize_ipv4(ip)
        return True
    except ValueError:
        return False


def validate_subnet(ip: str, subnet_cidr: str) -> bool:
    """
    Checks if an IPv4 address belongs to a given subnet CIDR (e.g. '10.189.149.0/24').
    Returns True if contained, False otherwise.
    """
    try:
        ip_obj = ipaddress.IPv4Address(normalize_ipv4(ip))
        net_obj = ipaddress.IPv4Network(subnet_cidr, strict=False)
        return ip_obj in net_obj
    except Exception:
        return False


def is_reserved_or_special_ip(ip: str, subnet_cidr: Optional[str] = None) -> bool:
    """
    Checks if IPv4 address is loopback, link-local, multicast, network ID, or broadcast address.
    """
    try:
        ip_obj = ipaddress.IPv4Address(normalize_ipv4(ip))
        if (
            ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
        ):
            return True

        if subnet_cidr:
            net_obj = ipaddress.IPv4Network(subnet_cidr, strict=False)
            if ip_obj == net_obj.network_address or ip_obj == net_obj.broadcast_address:
                return True
        return False
    except Exception:
        return True


def validate_hostname(hostname: str) -> bool:
    """Validates hostname compliance with RFC 1123."""
    if not hostname:
        return True  # Hostname is optional
    if len(hostname) > 63:
        return False
    return bool(HOSTNAME_REGEX.match(hostname))
