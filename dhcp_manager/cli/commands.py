"""
CLI Commands Execution Handler.
"""

import sys
from typing import List, Optional
from dhcp_manager.core.models import Assignment, ConflictSeverity
from dhcp_manager.core.validator import normalize_mac, normalize_ipv4
from dhcp_manager.core.conflict import ConflictDetector
from dhcp_manager.storage.database import Database
from dhcp_manager.storage.config import ConfigManager
from dhcp_manager.storage.backup import BackupManager
from dhcp_manager.root.executor import RootExecutor
from dhcp_manager.network.discovery import NetworkDiscovery
from dhcp_manager.network.neighbors import NeighborScanner
from dhcp_manager.dhcp.dnsmasq import DnsmasqBackend
from dhcp_manager.dhcp.android import AndroidTetheringBackend
from dhcp_manager.dhcp.generic import GenericLinuxBackend
from dhcp_manager.diagnostics.doctor import SystemDoctor


class CLIHandler:
    """Handles parsing and execution of CLI subcommands."""

    def __init__(self, dry_run: bool = False):
        self.config_mgr = ConfigManager()
        self.config = self.config_mgr.config
        if dry_run:
            self.config.dry_run = True

        self.db = Database(self.config.db_path)
        self.root_executor = RootExecutor(dry_run=self.config.dry_run)
        self.discovery = NetworkDiscovery(self.root_executor)
        self.scanner = NeighborScanner(self.root_executor)
        self.backup_mgr = BackupManager(self.db, self.config.backup_dir)

    def _get_active_backend(self):
        dnsmasq = DnsmasqBackend(self.root_executor)
        if dnsmasq.detect_active():
            return dnsmasq
        android = AndroidTetheringBackend(self.root_executor)
        if android.detect_active():
            return android
        return GenericLinuxBackend(self.root_executor)

    def cmd_status(self) -> int:
        state = self.discovery.discover_state()
        state.connected_clients = self.scanner.get_connected_clients(state.tether_interface)
        backend = self._get_active_backend()
        state.dhcp_leases = backend.parse_leases()

        print("==================================================")
        print("ANDROID ROOT DHCP MANAGER - NETWORK STATUS")
        print("==================================================")
        print(f"Tethering Active  : {'YES' if state.tethering_active else 'NO'}")
        print(f"Tether Interface  : {state.tether_interface or 'None (Hotspot inactive)'}")
        print(f"Gateway IPv4      : {state.gateway_ip or 'None'}")
        print(f"Subnet CIDR       : {state.subnet_cidr or 'None'}")
        print(f"Upstream Interface: {state.upstream_interface or 'Offline/Disconnected'}")
        print(f"DHCP Backend      : {backend.name}")
        print(f"Connected Clients : {len(state.connected_clients)}")
        print(f"Active DHCP Leases: {len(state.dhcp_leases)}")
        print(f"Managed Stored IP : {len(self.db.list_assignments())}")
        print(f"Root Status       : {'GRANTED' if self.root_executor.check_root() else 'UNAVAILABLE'}")
        print(f"Dry-Run Mode      : {'ENABLED' if self.config.dry_run else 'DISABLED'}")
        print("==================================================")
        return 0

    def cmd_list(self) -> int:
        assignments = self.db.list_assignments()
        if not assignments:
            print("No static IP assignments found in database.")
            print("Use 'dhcp-manager add --mac <MAC> --ip <IP>' to add one.")
            return 0

        print(f"{'ID':<4} {'MAC ADDRESS':<18} {'IPV4 ADDRESS':<16} {'STATUS':<8} {'HOSTNAME':<15} {'NOTES'}")
        print("-" * 75)
        for a in assignments:
            status = "ENABLED" if a.enabled else "DISABLED"
            hostname = (a.hostname[:14] + "…") if len(a.hostname) > 15 else a.hostname
            print(f"{a.id:<4} {a.mac_address:<18} {a.ipv4_address:<16} {status:<8} {hostname:<15} {a.notes}")
        return 0

    def cmd_add(self, mac: str, ip: str, hostname: str = "", notes: str = "", disabled: bool = False) -> int:
        net_state = self.discovery.discover_state()
        existing = self.db.list_assignments()
        detector = ConflictDetector(existing, net_state)

        conflicts = detector.check_assignment(mac, ip)
        has_error = False
        for c in conflicts:
            print(f"[{c.severity.value}] [{c.code}]: {c.message}")
            if c.severity == ConflictSeverity.ERROR:
                has_error = True

        if has_error:
            print("Error: Assignment rejected due to conflicts.")
            return 1

        norm_mac = normalize_mac(mac)
        norm_ip = normalize_ipv4(ip)
        asgn = Assignment(
            mac_address=norm_mac,
            ipv4_address=norm_ip,
            hostname=hostname,
            enabled=not disabled,
            notes=notes,
        )

        try:
            saved = self.db.add_assignment(asgn)
            print(f"Successfully added assignment #{saved.id}: {saved.mac_address} -> {saved.ipv4_address}")
            return 0
        except Exception as e:
            print(f"Failed to add assignment: {e}")
            return 1

    def cmd_remove(self, identifier: str) -> int:
        if self.db.delete_assignment(identifier):
            print(f"Successfully removed assignment '{identifier}'.")
            return 0
        else:
            print(f"Assignment '{identifier}' not found.")
            return 1

    def cmd_set_ip(self, mac: str, ip: str) -> int:
        existing = self.db.get_assignment_by_mac(mac)
        if existing:
            existing.ipv4_address = ip
            net_state = self.discovery.discover_state()
            detector = ConflictDetector(self.db.list_assignments(), net_state)
            conflicts = detector.check_assignment(mac, ip, ignore_assignment_id=existing.id)
            for c in conflicts:
                print(f"[{c.severity.value}] [{c.code}]: {c.message}")
                if c.severity == ConflictSeverity.ERROR:
                    return 1

            self.db.update_assignment(existing)
            print(f"Updated MAC '{mac}' IP to '{ip}'.")
            return 0
        else:
            return self.cmd_add(mac, ip)

    def cmd_enable_disable(self, identifier: str, enable: bool) -> int:
        if self.db.set_enabled(identifier, enable):
            action = "Enabled" if enable else "Disabled"
            print(f"Successfully {action} assignment '{identifier}'.")
            return 0
        else:
            print(f"Assignment '{identifier}' not found.")
            return 1

    def cmd_inspect(self, identifier: str) -> int:
        asgn = None
        if identifier.isdigit():
            asgn = self.db.get_assignment_by_id(int(identifier))
        if not asgn:
            asgn = self.db.get_assignment_by_mac(identifier)

        if not asgn:
            print(f"Assignment '{identifier}' not found.")
            return 1

        print("==================================================")
        print(f"ASSIGNMENT DETAILS #{asgn.id}")
        print("==================================================")
        print(f"MAC Address : {asgn.mac_address}")
        print(f"IPv4 Address: {asgn.ipv4_address}")
        print(f"Hostname    : {asgn.hostname or '(None)'}")
        print(f"Status      : {'ENABLED' if asgn.enabled else 'DISABLED'}")
        print(f"Notes       : {asgn.notes or '(None)'}")
        print(f"Created At  : {asgn.created_at}")
        print(f"Updated At  : {asgn.updated_at}")
        print(f"Last Seen   : {asgn.last_seen_at or 'Never'}")

        net_state = self.discovery.discover_state()
        clients = self.scanner.get_connected_clients(net_state.tether_interface)
        active_entry = next((c for c in clients if c.mac == asgn.mac_address), None)
        if active_entry:
            print(f"Active Status: CONNECTED on {active_entry.interface} (IP: {active_entry.ip}, State: {active_entry.state})")
        else:
            print("Active Status: DISCONNECTED / NOT IN ARP TABLE")

        print("==================================================")
        return 0

    def cmd_scan(self) -> int:
        net_state = self.discovery.discover_state()
        print(f"Scanning clients on tethering interface: {net_state.tether_interface or 'All interfaces'}...")
        clients = self.scanner.get_connected_clients(net_state.tether_interface)

        if not clients:
            print("No active clients detected in ARP/neighbor table.")
            return 0

        print(f"\n{'MAC ADDRESS':<18} {'CURRENT IP':<16} {'IFACE':<8} {'STATE':<10} {'MANAGED'}")
        print("-" * 65)

        assignments_by_mac = {a.mac_address: a for a in self.db.list_assignments()}
        for c in clients:
            managed_str = f"YES ({assignments_by_mac[c.mac].ipv4_address})" if c.mac in assignments_by_mac else "NO"
            print(f"{c.mac:<18} {c.ip:<16} {c.interface:<8} {c.state:<10} {managed_str}")

        return 0

    def cmd_conflicts(self) -> int:
        net_state = self.discovery.discover_state()
        assignments = self.db.list_assignments()
        detector = ConflictDetector(assignments, net_state)

        total_conflicts = 0
        print("Running conflict detection across all managed assignments...\n")
        for asgn in assignments:
            conflicts = detector.check_assignment(asgn.mac_address, asgn.ipv4_address, ignore_assignment_id=asgn.id)
            if conflicts:
                print(f"Assignment #{asgn.id} ({asgn.mac_address} -> {asgn.ipv4_address}):")
                for c in conflicts:
                    total_conflicts += 1
                    print(f"  - [{c.severity.value}] [{c.code}]: {c.message}")

        if total_conflicts == 0:
            print("No conflicts detected across any managed assignments.")
        else:
            print(f"\nFound {total_conflicts} total warnings/conflicts.")
        return 0

    def cmd_apply(self, dry_run: bool = False) -> int:
        if dry_run:
            self.root_executor.dry_run = True

        print("Applying static IP configuration to active DHCP/tethering server...")
        net_state = self.discovery.discover_state()
        backend = self._get_active_backend()
        assignments = self.db.list_assignments()

        success, messages = backend.apply_assignments(assignments, net_state)
        for msg in messages:
            print(f"  [APPLY] {msg}")

        if success:
            print("\nPerforming post-apply verification...")
            verified, v_messages = backend.verify_assignments(assignments, net_state)
            for v_msg in v_messages:
                print(f"  [VERIFY] {v_msg}")

            if verified:
                print("\nConfiguration applied and verified successfully.")
                return 0
            else:
                print("\nWarning: Configuration applied, but post-apply verification failed for some entries.")
                return 1
        else:
            print("\nError: Failed to apply configuration.")
            return 1

    def cmd_reload(self) -> int:
        backend = self._get_active_backend()
        if backend.reload_server():
            print(f"Successfully reloaded DHCP server ({backend.name}).")
            return 0
        else:
            print(f"Failed to reload DHCP server ({backend.name}).")
            return 1

    def cmd_backup(self, output_file: Optional[str] = None) -> int:
        if output_file:
            count = self.backup_mgr.export_assignments(output_file)
            print(f"Exported {count} assignments to '{output_file}'.")
        else:
            path = self.backup_mgr.create_backup()
            print(f"Created backup file: '{path}'.")
        return 0

    def cmd_restore(self, input_file: str, overwrite: bool = False) -> int:
        count, errors = self.backup_mgr.import_assignments(input_file, overwrite=overwrite)
        for err in errors:
            print(f"Warning: {err}")
        print(f"Imported {count} assignments from '{input_file}'.")
        return 0 if count > 0 else 1

    def cmd_doctor(self) -> int:
        doctor = SystemDoctor(self.root_executor, self.discovery)
        report = doctor.run_diagnostics()

        print("==================================================")
        print("ANDROID ROOT DHCP MANAGER - DIAGNOSTIC DOCTOR REPORT")
        print("==================================================")
        print(f"System OS   : {report.system_info['system']} {report.system_info['release']} ({report.system_info['machine']})")
        print(f"Python Ver  : {report.system_info['python_version']}")
        print("--------------------------------------------------")

        for c in report.checks:
            mark = "OK" if c.passed else "FAIL"
            print(f"[{mark:<4}] {c.name:<30}: {c.status}")
            if c.details:
                print(f"    Details    : {c.details}")
            if not c.passed and c.remediation:
                print(f"    Remediation: {c.remediation}")

        print("==================================================")
        if report.is_fully_supported:
            print("RESULT: System is READY and fully supported.")
            return 0
        else:
            print("RESULT: Some system checks failed or require attention.")
            return 1
