"""
SQLite Database storage for persistent static DHCP assignments with schema versioning.
"""

import contextlib
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import List, Optional, Union
from dhcp_manager.core.models import Assignment
from dhcp_manager.core.validator import normalize_mac, normalize_ipv4
from dhcp_manager.logging.logger import get_logger, Subsystem


CURRENT_SCHEMA_VERSION = 1
logger = get_logger(Subsystem.CONFIG)


class Database:
    """Manages SQLite persistent storage for static DHCP assignments."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is None:
            config_dir = Path.home() / ".config" / "android-root-dhcp-manager"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = config_dir / "dhcp_manager.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Create schema_version table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                )
                """
            )

            # Check existing version
            cursor.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (CURRENT_SCHEMA_VERSION,),
                )
                self._create_tables(cursor)
                conn.commit()
            else:
                version = row["version"]
                if version < CURRENT_SCHEMA_VERSION:
                    self._migrate(conn, version, CURRENT_SCHEMA_VERSION)

    def _create_tables(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT NOT NULL,
                ipv4_address TEXT NOT NULL,
                hostname TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_seen_at TEXT
            )
            """
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_assignments_mac ON assignments (mac_address)"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_assignments_ip ON assignments (ipv4_address)"
        )

    def _migrate(
        self, conn: sqlite3.Connection, old_ver: int, new_ver: int
    ) -> None:
        logger.info(f"Migrating database schema from v{old_ver} to v{new_ver}")
        cursor = conn.cursor()
        # Future migrations would be handled here
        cursor.execute("UPDATE schema_version SET version = ?", (new_ver,))
        conn.commit()

    def add_assignment(self, assignment: Assignment) -> Assignment:
        norm_mac = normalize_mac(assignment.mac_address)
        norm_ip = normalize_ipv4(assignment.ipv4_address)
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO assignments (
                    mac_address, ipv4_address, hostname, enabled, notes, created_at, updated_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    norm_mac,
                    norm_ip,
                    assignment.hostname.strip(),
                    1 if assignment.enabled else 0,
                    assignment.notes.strip(),
                    assignment.created_at or now_iso,
                    now_iso,
                    assignment.last_seen_at,
                ),
            )
            assignment.id = cursor.lastrowid
            assignment.mac_address = norm_mac
            assignment.ipv4_address = norm_ip
            conn.commit()
            logger.info(f"Added assignment: {norm_mac} -> {norm_ip} ({assignment.hostname})")
            return assignment

    def update_assignment(self, assignment: Assignment) -> Assignment:
        if assignment.id is None:
            existing = self.get_assignment_by_mac(assignment.mac_address)
            if existing is None or existing.id is None:
                raise ValueError("Cannot update assignment without valid ID or existing MAC")
            assignment.id = existing.id

        norm_mac = normalize_mac(assignment.mac_address)
        norm_ip = normalize_ipv4(assignment.ipv4_address)
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE assignments SET
                    mac_address = ?,
                    ipv4_address = ?,
                    hostname = ?,
                    enabled = ?,
                    notes = ?,
                    updated_at = ?,
                    last_seen_at = ?
                WHERE id = ?
                """,
                (
                    norm_mac,
                    norm_ip,
                    assignment.hostname.strip(),
                    1 if assignment.enabled else 0,
                    assignment.notes.strip(),
                    now_iso,
                    assignment.last_seen_at,
                    assignment.id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Assignment with ID {assignment.id} not found")
            conn.commit()
            assignment.mac_address = norm_mac
            assignment.ipv4_address = norm_ip
            assignment.updated_at = now_iso
            logger.info(f"Updated assignment ID {assignment.id}: {norm_mac} -> {norm_ip}")
            return assignment

    def delete_assignment(self, identifier: Union[int, str]) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(identifier, int) or (
                isinstance(identifier, str) and identifier.isdigit()
            ):
                cursor.execute("DELETE FROM assignments WHERE id = ?", (int(identifier),))
            else:
                norm_mac = normalize_mac(str(identifier))
                cursor.execute(
                    "DELETE FROM assignments WHERE mac_address = ?", (norm_mac,)
                )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info(f"Deleted assignment: {identifier}")
            return deleted

    def get_assignment_by_mac(self, mac: str) -> Optional[Assignment]:
        try:
            norm_mac = normalize_mac(mac)
        except ValueError:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM assignments WHERE mac_address = ?", (norm_mac,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_assignment(row)
            return None

    def get_assignment_by_id(self, asgn_id: int) -> Optional[Assignment]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assignments WHERE id = ?", (asgn_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_assignment(row)
            return None

    def list_assignments(self) -> List[Assignment]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assignments ORDER BY ipv4_address ASC")
            rows = cursor.fetchall()
            return [self._row_to_assignment(r) for r in rows]

    def set_enabled(self, identifier: Union[int, str], enabled: bool) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            val = 1 if enabled else 0
            now_iso = datetime.now(timezone.utc).isoformat()
            if isinstance(identifier, int) or (
                isinstance(identifier, str) and identifier.isdigit()
            ):
                cursor.execute(
                    "UPDATE assignments SET enabled = ?, updated_at = ? WHERE id = ?",
                    (val, now_iso, int(identifier)),
                )
            else:
                norm_mac = normalize_mac(str(identifier))
                cursor.execute(
                    "UPDATE assignments SET enabled = ?, updated_at = ? WHERE mac_address = ?",
                    (val, now_iso, norm_mac),
                )
            conn.commit()
            return cursor.rowcount > 0

    def update_last_seen(self, mac: str, timestamp_iso: Optional[str] = None) -> bool:
        try:
            norm_mac = normalize_mac(mac)
        except ValueError:
            return False

        ts = timestamp_iso or datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE assignments SET last_seen_at = ? WHERE mac_address = ?",
                (ts, norm_mac),
            )
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_assignment(self, row: sqlite3.Row) -> Assignment:
        return Assignment(
            id=row["id"],
            mac_address=row["mac_address"],
            ipv4_address=row["ipv4_address"],
            hostname=row["hostname"] or "",
            enabled=bool(row["enabled"]),
            notes=row["notes"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_seen_at=row["last_seen_at"],
        )
