"""
Unit tests for Backup, Export, and Import functionality.
"""

import os
import tempfile
import unittest
from dhcp_manager.core.models import Assignment
from dhcp_manager.storage.database import Database
from dhcp_manager.storage.backup import BackupManager


class TestBackupManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.backup_dir = os.path.join(self.temp_dir.name, "backups")
        self.db = Database(self.db_path)
        self.backup_mgr = BackupManager(self.db, self.backup_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_and_import(self):
        self.db.add_assignment(
            Assignment(mac_address="28:3f:69:64:69:73", ipv4_address="10.189.149.16", hostname="Laptop")
        )
        self.db.add_assignment(
            Assignment(mac_address="aa:bb:cc:dd:ee:ff", ipv4_address="10.189.149.17", hostname="Phone")
        )

        export_file = os.path.join(self.temp_dir.name, "export.json")
        exported_count = self.backup_mgr.export_assignments(export_file)
        self.assertEqual(exported_count, 2)
        self.assertTrue(os.path.exists(export_file))

        # Create fresh DB and import
        db2_path = os.path.join(self.temp_dir.name, "test2.db")
        db2 = Database(db2_path)
        backup_mgr2 = BackupManager(db2, self.backup_dir)

        imported_count, errors = backup_mgr2.import_assignments(export_file)
        self.assertEqual(imported_count, 2)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(db2.list_assignments()), 2)

    def test_automated_backup_creation(self):
        self.db.add_assignment(Assignment(mac_address="28:3f:69:64:69:73", ipv4_address="10.189.149.16"))
        path = self.backup_mgr.create_backup()
        self.assertTrue(os.path.exists(path))
        self.assertGreater(len(self.backup_mgr.list_backups()), 0)


if __name__ == "__main__":
    unittest.main()
