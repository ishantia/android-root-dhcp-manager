"""
Unit tests for System Doctor diagnostics report.
Author: ishantia
"""

import unittest
from dhcp_manager.root.executor import RootExecutor
from dhcp_manager.network.discovery import NetworkDiscovery
from dhcp_manager.diagnostics.doctor import SystemDoctor


class TestSystemDoctor(unittest.TestCase):

    def test_run_diagnostics(self):
        executor = RootExecutor(dry_run=True)
        discovery = NetworkDiscovery(executor)
        doctor = SystemDoctor(executor, discovery)

        report = doctor.run_diagnostics()
        self.assertIsNotNone(report)
        self.assertGreater(len(report.checks), 0)
        self.assertIn("system", report.system_info)


if __name__ == "__main__":
    unittest.main()
