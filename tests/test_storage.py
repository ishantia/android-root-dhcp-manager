"""
Unit tests for SQLite Database persistence, schema migrations, and CRUD operations.
"""

import os
import tempfile
import unittest
from dhcp_manager.core.models import Assignment
from dhcp_manager.storage.database import Database


class TestDatabase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_dhcp.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_get_assignment(self):
        asgn = Assignment(
            mac_address="28:3F:69:64:69:73",
            ipv4_address="10.189.149.16",
            hostname="My-Laptop",
            notes="Testing",
        )
        saved = self.db.add_assignment(asgn)
        self.assertIsNotNone(saved.id)
        self.assertEqual(saved.mac_address, "28:3f:69:64:69:73")

        fetched = self.db.get_assignment_by_mac("28:3f:69:64:69:73")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.ipv4_address, "10.189.149.16")
        self.assertEqual(fetched.hostname, "My-Laptop")

    def test_update_assignment(self):
        asgn = Assignment(
            mac_address="28:3F:69:64:69:73",
            ipv4_address="10.189.149.16",
            hostname="OldHost",
        )
        saved = self.db.add_assignment(asgn)

        saved.ipv4_address = "10.189.149.99"
        saved.hostname = "NewHost"
        updated = self.db.update_assignment(saved)

        self.assertEqual(updated.ipv4_address, "10.189.149.99")

        fetched = self.db.get_assignment_by_id(saved.id)
        self.assertEqual(fetched.hostname, "NewHost")
        self.assertEqual(fetched.ipv4_address, "10.189.149.99")

    def test_delete_assignment(self):
        asgn = Assignment(
            mac_address="28:3F:69:64:69:73",
            ipv4_address="10.189.149.16",
        )
        saved = self.db.add_assignment(asgn)
        self.assertTrue(self.db.delete_assignment(saved.id))
        self.assertIsNone(self.db.get_assignment_by_id(saved.id))

    def test_unique_indexes(self):
        asgn1 = Assignment(mac_address="28:3F:69:64:69:73", ipv4_address="10.189.149.16")
        self.db.add_assignment(asgn1)

        # Duplicate MAC
        asgn2 = Assignment(mac_address="28:3F:69:64:69:73", ipv4_address="10.189.149.17")
        with self.assertRaises(Exception):
            self.db.add_assignment(asgn2)

    def test_list_assignments(self):
        self.db.add_assignment(Assignment(mac_address="11:11:11:11:11:11", ipv4_address="10.189.149.20"))
        self.db.add_assignment(Assignment(mac_address="22:22:22:22:22:22", ipv4_address="10.189.149.10"))

        all_asgns = self.db.list_assignments()
        self.assertEqual(len(all_asgns), 2)
        # Should be ordered by IPv4 ASC
        self.assertEqual(all_asgns[0].ipv4_address, "10.189.149.10")


if __name__ == "__main__":
    unittest.main()
