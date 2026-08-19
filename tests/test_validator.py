"""
Unit tests for MAC, IPv4, Subnet, and Hostname validation.
"""

import unittest
from dhcp_manager.core.validator import (
    normalize_mac,
    is_valid_mac,
    is_private_mac,
    normalize_ipv4,
    is_valid_ipv4,
    validate_subnet,
    is_reserved_or_special_ip,
    validate_hostname,
)


class TestValidator(unittest.TestCase):

    def test_mac_normalization(self):
        self.assertEqual(normalize_mac("28:3F:69:64:69:73"), "28:3f:69:64:69:73")
        self.assertEqual(normalize_mac("28-3f-69-64-69-73"), "28:3f:69:64:69:73")
        self.assertEqual(normalize_mac("283f.6964.6973"), "28:3f:69:64:69:73")
        self.assertEqual(normalize_mac("283F69646973"), "28:3f:69:64:69:73")

    def test_invalid_mac(self):
        self.assertFalse(is_valid_mac("invalid_mac"))
        self.assertFalse(is_valid_mac("28:3F:69:64:69"))
        self.assertFalse(is_valid_mac("28:3F:69:64:69:73:88"))
        self.assertFalse(is_valid_mac("ZZ:3F:69:64:69:73"))

    def test_private_mac(self):
        # Locally administered bit set (second digit 2, 6, A, E)
        self.assertTrue(is_private_mac("02:00:00:00:00:00"))
        self.assertTrue(is_private_mac("a6:3f:69:64:69:73"))
        self.assertFalse(is_private_mac("28:3f:69:64:69:73"))

    def test_ipv4_normalization(self):
        self.assertEqual(normalize_ipv4("10.189.149.16"), "10.189.149.16")
        self.assertEqual(normalize_ipv4(" 192.168.1.1 "), "192.168.1.1")
        self.assertTrue(is_valid_ipv4("10.0.0.1"))
        self.assertFalse(is_valid_ipv4("256.0.0.1"))
        self.assertFalse(is_valid_ipv4("10.0.0"))

    def test_subnet_validation(self):
        subnet = "10.189.149.0/24"
        self.assertTrue(validate_subnet("10.189.149.16", subnet))
        self.assertTrue(validate_subnet("10.189.149.185", subnet))
        self.assertFalse(validate_subnet("10.189.150.1", subnet))
        self.assertFalse(validate_subnet("192.168.1.1", subnet))

    def test_reserved_ip(self):
        subnet = "10.189.149.0/24"
        self.assertTrue(is_reserved_or_special_ip("127.0.0.1"))
        self.assertTrue(is_reserved_or_special_ip("169.254.1.1"))
        self.assertTrue(is_reserved_or_special_ip("10.189.149.0", subnet))  # Network ID
        self.assertTrue(is_reserved_or_special_ip("10.189.149.255", subnet))  # Broadcast
        self.assertFalse(is_reserved_or_special_ip("10.189.149.16", subnet))

    def test_hostname(self):
        self.assertTrue(validate_hostname("my-laptop"))
        self.assertTrue(validate_hostname("android123"))
        self.assertTrue(validate_hostname(""))
        self.assertFalse(validate_hostname("-invalid"))
        self.assertFalse(validate_hostname("invalid_host!"))


if __name__ == "__main__":
    unittest.main()
