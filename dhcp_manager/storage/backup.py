"""
Backup, Export, Import, and Restore functionality.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import List, Tuple, Optional, Union
from dhcp_manager.core.models import Assignment
from dhcp_manager.core.validator import is_valid_mac, is_valid_ipv4, normalize_mac, normalize_ipv4
from dhcp_manager.storage.database import Database, CURRENT_SCHEMA_VERSION
from dhcp_manager.logging.logger import get_logger, Subsystem


logger = get_logger(Subsystem.CONFIG)


class BackupManager:
    """Handles assignment export/import and automated database backups."""

    def __init__(self, db: Database, backup_dir: Optional[Union[str, Path]] = None):
        self.db = db
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            self.backup_dir = Path.home() / ".config" / "android-root-dhcp-manager" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def export_assignments(self, export_path: Union[str, Path]) -> int:
        assignments = self.db.list_assignments()
        export_data = {
            "version": CURRENT_SCHEMA_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(assignments),
            "assignments": [asgn.to_dict() for asgn in assignments],
        }

        path = Path(export_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported {len(assignments)} assignments to {path}")
        return len(assignments)

    def import_assignments(
        self, import_path: Union[str, Path], overwrite: bool = False
    ) -> Tuple[int, List[str]]:
        """
        Imports assignments from a JSON file.
        Returns tuple of (imported_count, error_messages).
        """
        path = Path(import_path)
        if not path.exists():
            return 0, [f"File not found: '{import_path}'"]

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return 0, [f"Failed to parse JSON file '{import_path}': {e}"]

        raw_list = data.get("assignments", [])
        if not isinstance(raw_list, list):
            return 0, ["Invalid format: 'assignments' field must be a list."]

        imported_count = 0
        errors: List[str] = []

        existing = {asgn.mac_address: asgn for asgn in self.db.list_assignments()}

        for idx, item in enumerate(raw_list):
            mac = item.get("mac_address")
            ip = item.get("ipv4_address")

            if not mac or not is_valid_mac(mac):
                errors.append(f"Item #{idx + 1}: Invalid MAC address '{mac}'")
                continue
            if not ip or not is_valid_ipv4(ip):
                errors.append(f"Item #{idx + 1}: Invalid IPv4 address '{ip}'")
                continue

            norm_mac = normalize_mac(mac)
            norm_ip = normalize_ipv4(ip)

            asgn = Assignment(
                mac_address=norm_mac,
                ipv4_address=norm_ip,
                hostname=item.get("hostname", ""),
                enabled=bool(item.get("enabled", True)),
                notes=item.get("notes", ""),
            )

            if norm_mac in existing:
                if overwrite:
                    asgn.id = existing[norm_mac].id
                    self.db.update_assignment(asgn)
                    imported_count += 1
                else:
                    errors.append(
                        f"Item #{idx + 1}: MAC '{norm_mac}' already exists (skipped, overwrite=False)"
                    )
            else:
                self.db.add_assignment(asgn)
                imported_count += 1

        logger.info(f"Imported {imported_count} assignments from {path} with {len(errors)} warnings/errors.")
        return imported_count, errors

    def create_backup(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"assignments_backup_{timestamp}.json"
        self.export_assignments(backup_file)
        return backup_file

    def list_backups(self) -> List[Path]:
        return sorted(list(self.backup_dir.glob("assignments_backup_*.json")), reverse=True)
