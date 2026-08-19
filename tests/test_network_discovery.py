"""
Unit tests for Network Discovery and route/addr parsing.
"""

import unittest
from dhcp_manager.root.executor import RootExecutor
from dhcp_manager.network.discovery import NetworkDiscovery
from dhcp_manager.network.neighbors import NeighborScanner


class TestNetworkDiscovery(unittest.TestCase):

    def setUp(self):
        self.executor = RootExecutor(dry_run=True)
        self.discovery = NetworkDiscovery(self.executor)

    def test_parse_tether_route(self):
        sample_route_output = (
            "10.189.149.0/24 dev ap0 proto kernel scope link src 10.189.149.185\n"
            "default via 10.10.14.1 dev tun0\n"
        )
        iface, gw, subnet = self.discovery._parse_tether_route(sample_route_output)
        self.assertEqual(iface, "ap0")
        self.assertEqual(gw, "10.189.149.185")
        self.assertEqual(subnet, "10.189.149.0/24")

    def test_parse_tether_addr(self):
        sample_addr_output = (
            "1: lo: <LOOPBACK,UP> ...\n"
            "    inet 127.0.0.1/8 scope host lo\n"
            "15: ap0: <BROADCAST,MULTICAST,UP> ...\n"
            "    inet 192.168.43.1/24 brd 192.168.43.255 scope global ap0\n"
        )
        iface, gw, subnet = self.discovery._parse_tether_addr(sample_addr_output)
        self.assertEqual(iface, "ap0")
        self.assertEqual(gw, "192.168.43.1")
        self.assertEqual(subnet, "192.168.43.0/24")


class TestNeighborScanner(unittest.TestCase):

    def test_parse_ip_neigh(self):
        executor = RootExecutor(dry_run=True)
        scanner = NeighborScanner(executor)
        # Mock parsing logic implicitly
        entries = scanner._scan_ip_neigh(None)
        self.assertIsInstance(entries, list)


if __name__ == "__main__":
    unittest.main()
