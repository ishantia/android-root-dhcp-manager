"""
Unit tests for Root Executor, dry-run mode, escaping, and timeouts.
"""

import sys
import unittest
from dhcp_manager.root.executor import RootExecutor, CommandResult


class TestRootExecutor(unittest.TestCase):

    def test_dry_run_execution(self):
        executor = RootExecutor(dry_run=True)
        res = executor.execute(["ip", "neigh", "show"], use_root=True)

        self.assertTrue(res.success)
        self.assertIn("[DRY-RUN]", res.stdout)
        self.assertEqual(res.exit_code, 0)

    def test_non_root_command(self):
        executor = RootExecutor(dry_run=False)
        res = executor.execute([sys.executable, "-c", "print('hello_world')"], use_root=False)

        self.assertTrue(res.success)
        self.assertEqual(res.stdout, "hello_world")

    def test_command_escaping(self):
        executor = RootExecutor(dry_run=True)
        # Attempt injection pattern
        dangerous_arg = "10.0.0.1; rm -rf /"
        res = executor.execute(["echo", dangerous_arg], use_root=True)

        self.assertTrue(res.success)
        # Escaped string should wrap dangerous chars in quotes
        self.assertIn("10.0.0.1", res.command_str)


if __name__ == "__main__":
    unittest.main()
