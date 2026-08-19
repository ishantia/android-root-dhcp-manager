"""
Unit tests for IP & MAC Conflict Detection.
Author: ishantia
"""

import unittest
from dhcp_manager.core.models import (
    Assignment,
    NetworkState,
    NeighborEntry,
    DHCPLease,
    ConflictSeverity,
)
from dhcp_manager.core.conflict import ConflictDetector


class TestConflictDetector(unittest.TestCase):

    def setUp(self):
        self.existing_assignments = [
            Assignment(
                id=1,
                mac_address="28:3f:69:64:69:73",
                ipv4_address="10.189.149.16",
                hostname="Laptop",
            ),
            Assignment(
                id=2,
                mac_address="aa:bb:cc:dd:ee:ff",
                ipv4_address="10.189.149.17",
                hostname="Phone",
            ),
        ]
        self.net_state = NetworkState(
            tethering_active=True,
            tether_interface="ap0",
            gateway_ip="10.189.149.185",
            subnet_cidr="10.189.149.0/24",
            connected_clients=[
                NeighborEntry(
                    ip="10.189.149.50",
                    mac="11:22:33:44:55:66",
                    interface="ap0",
                    state="REACHABLE",
                )
            ],
            dhcp_leases=[
                DHCPLease(
                    expiry_timestamp=1700000000,
                    mac="99:88:77:66:55:44",
                    ip="10.189.149.60",
                )
            ],
        )
        self.detector = ConflictDetector(self.existing_assignments, self.net_state)

    def test_no_conflict(self):
        conflicts = self.detector.check_assignment("00:11:22:33:44:55", "10.189.149.20")
        self.assertEqual(len(conflicts), 0)

    def test_invalid_mac_or_ip(self):
        conflicts_mac = self.detector.check_assignment("invalid_mac", "10.189.149.20")
        self.assertTrue(any(c.code == "INVALID_MAC" for c in conflicts_mac))

        conflicts_ip = self.detector.check_assignment("00:11:22:33:44:55", "999.999.1.1")
        self.assertTrue(any(c.code == "INVALID_IP" for c in conflicts_ip))

    def test_gateway_collision(self):
        conflicts = self.detector.check_assignment("00:11:22:33:44:55", "10.189.149.185")
        self.assertTrue(any(c.code == "GATEWAY_COLLISION" for c in conflicts))

    def test_out_of_subnet(self):
        conflicts = self.detector.check_assignment("00:11:22:33:44:55", "192.168.1.50")
        self.assertTrue(any(c.code == "OUT_OF_SUBNET" for c in conflicts))

    def test_db_ip_collision(self):
        conflicts = self.detector.check_assignment("00:11:22:33:44:55", "10.189.149.16")
        self.assertTrue(any(c.code == "DB_IP_COLLISION" for c in conflicts))

    def test_active_neighbor_collision(self):
        conflicts = self.detector.check_assignment("00:11:22:33:44:55", "10.189.149.50")
        self.assertTrue(any(c.code == "ACTIVE_IP_IN_USE" for c in conflicts))

    def test_dhcp_lease_collision(self):
        conflicts = self.detector.check_assignment("00:11:22:33:44:55", "10.189.149.60")
        self.assertTrue(any(c.code == "DHCP_LEASE_COLLISION" for c in conflicts))


if __name__ == "__main__":
    unittest.main()
