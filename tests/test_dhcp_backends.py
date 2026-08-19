"""
Unit tests for Dnsmasq, Android Netd, and Generic Linux DHCP Backends.
"""

import unittest
from dhcp_manager.core.models import Assignment, NetworkState
from dhcp_manager.root.executor import RootExecutor
from dhcp_manager.dhcp.dnsmasq import DnsmasqBackend
from dhcp_manager.dhcp.android import AndroidTetheringBackend


class TestDHCPBackends(unittest.TestCase):

    def setUp(self):
        self.executor = RootExecutor(dry_run=True)
        self.dnsmasq_backend = DnsmasqBackend(self.executor)
        self.android_backend = AndroidTetheringBackend(self.executor)

    def test_dnsmasq_cmdline_extraction(self):
        cmd = "/system/bin/dnsmasq --dhcp-leasefile=/data/misc/dhcp/dnsmasq.leases --addn-hosts=/data/misc/dhcp/dnsmasq.hosts --conf-dir=/data/misc/dhcp/dnsmasq.d"
        self.dnsmasq_backend._extract_paths_from_cmdline(cmd)

        self.assertEqual(self.dnsmasq_backend.lease_file, "/data/misc/dhcp/dnsmasq.leases")
        self.assertEqual(self.dnsmasq_backend.hosts_file, "/data/misc/dhcp/dnsmasq.hosts")
        self.assertEqual(self.dnsmasq_backend.conf_dir, "/data/misc/dhcp/dnsmasq.d")

    def test_dnsmasq_conf_generation(self):
        asgns = [
            Assignment(mac_address="28:3f:69:64:69:73", ipv4_address="10.189.149.16", hostname="Laptop"),
            Assignment(mac_address="aa:bb:cc:dd:ee:ff", ipv4_address="10.189.149.17"),
        ]
        success, msg = self.dnsmasq_backend._write_dnsmasq_conf("/data/misc/dhcp/dnsmasq.d", asgns)
        self.assertTrue(success)

    def test_android_backend_apply(self):
        asgns = [
            Assignment(mac_address="28:3f:69:64:69:73", ipv4_address="10.189.149.16"),
        ]
        net_state = NetworkState(tethering_active=True, tether_interface="ap0")
        success, messages = self.android_backend.apply_assignments(asgns, net_state)
        self.assertTrue(success)
        self.assertGreater(len(messages), 0)


if __name__ == "__main__":
    unittest.main()
