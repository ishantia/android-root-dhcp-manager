"""
Terminal User Interface (TUI) Dashboard for Android Root DHCP Manager.
Provides interactive keyboard navigation, status monitoring, management, forms, and diagnostic screens.
Author: ishantia
"""

import curses
import os
import sys
import time
from typing import List, Optional
from dhcp_manager.core.models import Assignment, NeighborEntry, NetworkState
from dhcp_manager.core.conflict import ConflictDetector
from dhcp_manager.cli.commands import CLIHandler


class DHCPManagerTUI:
    """Curses-based TUI Dashboard for Android Root DHCP Manager."""

    def __init__(self, stdscr, handler: CLIHandler):
        self.stdscr = stdscr
        self.handler = handler
        self.selected_index = 0
        self.active_tab = 0  # 0: Assignments, 1: Active Clients, 2: Doctor
        self.status_msg = "Press [A] Add | [E] Edit | [D] Delete | [P] Apply | [R] Refresh | [Q] Quit"
        self.assignments: List[Assignment] = []
        self.connected_clients: List[NeighborEntry] = []
        self.net_state: NetworkState = NetworkState()

    def safe_addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        """Safely writes string to curses screen without throwing bottom-right corner or boundary ERR."""
        try:
            height, width = self.stdscr.getmaxyx()
            if y < 0 or y >= height or x < 0 or x >= width:
                return
            
            # Truncate text to fit within window width
            max_len = width - x
            if y == height - 1:
                max_len = max(0, max_len - 1)  # Prevent bottom-right corner cursor overflow
            
            if max_len <= 0:
                return
                
            truncated = text[:max_len]
            if attr:
                self.stdscr.addstr(y, x, truncated, attr)
            else:
                self.stdscr.addstr(y, x, truncated)
        except Exception:
            pass

    def run(self) -> int:
        try:
            curses.curs_set(0)
        except Exception:
            pass

        self.stdscr.nodelay(False)
        self.stdscr.keypad(True)

        if curses.has_colors():
            try:
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)    # Header / Highlight
                curses.init_pair(2, curses.COLOR_GREEN, -1)                  # Status OK
                curses.init_pair(3, curses.COLOR_YELLOW, -1)                 # Warnings
                curses.init_pair(4, curses.COLOR_RED, -1)                    # Errors
                curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)   # Active Tab
            except Exception:
                pass

        self.refresh_data()

        while True:
            self.draw()
            try:
                ch = self.stdscr.getch()
            except Exception:
                break

            if ch in (ord('q'), ord('Q')):
                break
            elif ch in (ord('r'), ord('R')):
                self.refresh_data()
                self.status_msg = "Refreshed network status and client list."
            elif ch == curses.KEY_DOWN or ch == ord('j'):
                self.move_selection(1)
            elif ch == curses.KEY_UP or ch == ord('k'):
                self.move_selection(-1)
            elif ch == ord('\t'):
                self.active_tab = (self.active_tab + 1) % 3
                self.selected_index = 0
            elif ch in (ord('a'), ord('A')):
                self.action_add()
            elif ch in (ord('e'), ord('E')):
                self.action_edit()
            elif ch in (ord('d'), ord('D')):
                self.action_delete()
            elif ch in (ord('p'), ord('P')):
                self.action_apply()
            elif ch in (ord('c'), ord('C')):
                self.action_conflicts()
            elif ch in (ord('l'), ord('L')):
                self.active_tab = 2

        return 0

    def refresh_data(self) -> None:
        try:
            self.assignments = self.handler.db.list_assignments()
            self.net_state = self.handler.discovery.discover_state()
            self.connected_clients = self.handler.scanner.get_connected_clients(self.net_state.tether_interface)
        except Exception as e:
            self.status_msg = f"Data refresh warning: {e}"

    def move_selection(self, delta: int) -> None:
        max_items = len(self.assignments) if self.active_tab == 0 else len(self.connected_clients)
        if max_items > 0:
            self.selected_index = max(0, min(max_items - 1, self.selected_index + delta))

    def draw(self) -> None:
        try:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()

            if height < 12 or width < 50:
                self.safe_addstr(0, 0, "Terminal window too small.")
                self.stdscr.refresh()
                return

            # 1. Header Bar
            header = " ANDROID ROOT DHCP MANAGER v1.0.0 "
            tether_str = f"Tethering: [{'ACTIVE' if self.net_state.tethering_active else 'INACTIVE'}]"
            root_str = f"Root: [{'YES' if self.handler.root_executor.check_root() else 'NO'}]"
            title_line = f"{header:<35} {tether_str:<20} {root_str:>15}"
            
            header_attr = curses.color_pair(1) if curses.has_colors() else curses.A_REVERSE
            self.safe_addstr(0, 0, title_line.ljust(width), header_attr)

            # 2. Network Overview Panel
            backend = self.handler._get_active_backend().name
            net_info = (
                f"Interface: {self.net_state.tether_interface or 'None'} | "
                f"Gateway: {self.net_state.gateway_ip or 'None'} | "
                f"Subnet: {self.net_state.subnet_cidr or 'None'} | "
                f"Upstream: {self.net_state.upstream_interface or 'None'} | "
                f"Backend: {backend}"
            )
            self.safe_addstr(2, 2, net_info)

            # 3. Tabs (0: Stored Assignments, 1: Connected Clients, 2: System Status)
            tab0 = "[1] Managed Assignments "
            tab1 = "[2] Connected Clients "
            tab2 = "[3] System Overview "

            self.safe_addstr(4, 2, "Tabs: ")
            self.draw_tab(4, 8, tab0, self.active_tab == 0)
            self.draw_tab(4, 32, tab1, self.active_tab == 1)
            self.draw_tab(4, 55, tab2, self.active_tab == 2)

            self.safe_addstr(5, 0, "-" * (width - 1))

            # 4. Content Area
            content_height = height - 7
            if self.active_tab == 0:
                self.draw_assignments_view(6, content_height, width)
            elif self.active_tab == 1:
                self.draw_clients_view(6, content_height, width)
            else:
                self.draw_doctor_view(6, content_height, width)

            # 5. Status / Controls Footer
            footer = f" {self.status_msg} ".ljust(width - 1)
            self.safe_addstr(height - 1, 0, footer, header_attr)

            self.stdscr.refresh()
        except Exception:
            pass

    def draw_tab(self, y: int, x: int, label: str, is_active: bool) -> None:
        if is_active:
            attr = curses.color_pair(5) if curses.has_colors() else curses.A_BOLD
            self.safe_addstr(y, x, label, attr)
        else:
            self.safe_addstr(y, x, label)

    def draw_assignments_view(self, start_y: int, max_lines: int, width: int) -> None:
        headers = f"{'ID':<4} {'MAC ADDRESS':<18} {'IPV4 ADDRESS':<16} {'STATUS':<8} {'HOSTNAME':<15} {'NOTES'}"
        self.safe_addstr(start_y, 2, headers, curses.A_BOLD)

        if not self.assignments:
            self.safe_addstr(start_y + 2, 4, "No static IP assignments stored. Press 'A' to add one.")
            return

        for idx, a in enumerate(self.assignments[: max_lines - 2]):
            y = start_y + 1 + idx
            status = "ENABLED" if a.enabled else "DISABLED"
            hostname = (a.hostname[:14] + "…") if len(a.hostname) > 15 else a.hostname
            line = f"{a.id:<4} {a.mac_address:<18} {a.ipv4_address:<16} {status:<8} {hostname:<15} {a.notes}"

            if idx == self.selected_index:
                self.safe_addstr(y, 2, line.ljust(width - 4), curses.A_REVERSE)
            else:
                self.safe_addstr(y, 2, line)

    def draw_clients_view(self, start_y: int, max_lines: int, width: int) -> None:
        headers = f"{'MAC ADDRESS':<18} {'CURRENT IP':<16} {'IFACE':<8} {'STATE':<10} {'MANAGED'}"
        self.safe_addstr(start_y, 2, headers, curses.A_BOLD)

        if not self.connected_clients:
            self.safe_addstr(start_y + 2, 4, "No active clients detected on tethering interface.")
            return

        assignments_by_mac = {a.mac_address: a for a in self.assignments}
        for idx, c in enumerate(self.connected_clients[: max_lines - 2]):
            y = start_y + 1 + idx
            managed = f"YES ({assignments_by_mac[c.mac].ipv4_address})" if c.mac in assignments_by_mac else "NO"
            line = f"{c.mac:<18} {c.ip:<16} {c.interface:<8} {c.state:<10} {managed}"

            if idx == self.selected_index:
                self.safe_addstr(y, 2, line.ljust(width - 4), curses.A_REVERSE)
            else:
                self.safe_addstr(y, 2, line)

    def draw_doctor_view(self, start_y: int, max_lines: int, width: int) -> None:
        self.safe_addstr(start_y, 2, "System Status Overview", curses.A_BOLD)
        backend = self.handler._get_active_backend().name
        lines = [
            f"Tethering Active  : {'YES' if self.net_state.tethering_active else 'NO'}",
            f"Tether Interface  : {self.net_state.tether_interface or 'None (Hotspot inactive)'}",
            f"Gateway IPv4      : {self.net_state.gateway_ip or 'None'}",
            f"Subnet CIDR       : {self.net_state.subnet_cidr or 'None'}",
            f"Upstream Interface: {self.net_state.upstream_interface or 'Offline/Disconnected'}",
            f"DHCP Backend      : {backend}",
            f"Connected Clients : {len(self.connected_clients)}",
            f"Managed Stored IP : {len(self.assignments)}",
            f"Root Status       : {'GRANTED' if self.handler.root_executor.check_root() else 'UNAVAILABLE'}",
        ]
        for idx, line in enumerate(lines[: max_lines - 2]):
            self.safe_addstr(start_y + 2 + idx, 4, line)

    def prompt_input(self, title: str, fields: List[str]) -> Optional[List[str]]:
        try:
            curses.echo()
            try:
                curses.curs_set(1)
            except Exception:
                pass

            height, width = self.stdscr.getmaxyx()
            win = curses.newwin(len(fields) + 6, min(50, width - 6), 4, 3)
            win.box()
            win.addstr(1, 2, f"=== {title} ===", curses.A_BOLD)

            results: List[str] = []
            for idx, field_name in enumerate(fields):
                win.addstr(idx + 3, 2, f"{field_name[:15]}: ")
                win.refresh()
                inp = win.getstr(idx + 3, len(field_name[:15]) + 4, 30).decode("utf-8").strip()
                results.append(inp)

            curses.noecho()
            try:
                curses.curs_set(0)
            except Exception:
                pass
            return results
        except Exception:
            return None

    def action_add(self) -> None:
        res = self.prompt_input("Add Assignment", ["MAC Address", "IPv4 Address", "Hostname (opt)"])
        if res and len(res) >= 2 and res[0] and res[1]:
            mac, ip = res[0], res[1]
            host = res[2] if len(res) > 2 else ""
            exit_code = self.handler.cmd_add(mac=mac, ip=ip, hostname=host)
            if exit_code == 0:
                self.status_msg = f"Successfully added {mac} -> {ip}"
            else:
                self.status_msg = "Error adding assignment. Check conflicts."
            self.refresh_data()

    def action_edit(self) -> None:
        if not self.assignments or self.selected_index >= len(self.assignments):
            self.status_msg = "No assignment selected to edit."
            return

        asgn = self.assignments[self.selected_index]
        res = self.prompt_input(f"Edit Assignment #{asgn.id}", [f"IPv4 ({asgn.ipv4_address})", f"Hostname ({asgn.hostname})"])
        if res and res[0]:
            new_ip = res[0] or asgn.ipv4_address
            new_host = res[1] if res[1] else asgn.hostname
            exit_code = self.handler.cmd_set_ip(asgn.mac_address, new_ip)
            if exit_code == 0:
                self.status_msg = f"Updated MAC {asgn.mac_address} to IP {new_ip}"
            else:
                self.status_msg = "Error updating assignment."
            self.refresh_data()

    def action_delete(self) -> None:
        if not self.assignments or self.selected_index >= len(self.assignments):
            self.status_msg = "No assignment selected to delete."
            return

        asgn = self.assignments[self.selected_index]
        self.handler.cmd_remove(str(asgn.id))
        self.status_msg = f"Deleted assignment #{asgn.id} ({asgn.mac_address})"
        self.refresh_data()

    def action_apply(self) -> None:
        self.status_msg = "Applying static DHCP configuration..."
        self.draw()
        exit_code = self.handler.cmd_apply()
        if exit_code == 0:
            self.status_msg = "Successfully applied static IP configuration!"
        else:
            self.status_msg = "Apply completed with warnings or errors. Check logs."

    def action_conflicts(self) -> None:
        self.status_msg = "Checking network conflicts..."
        net_state = self.handler.discovery.discover_state()
        detector = ConflictDetector(self.assignments, net_state)
        has_conflicts = False
        for asgn in self.assignments:
            c_list = detector.check_assignment(asgn.mac_address, asgn.ipv4_address, ignore_assignment_id=asgn.id)
            if c_list:
                has_conflicts = True
                break
        if has_conflicts:
            self.status_msg = "WARNING: Conflicts detected! Run 'dhcp-manager conflicts' in CLI for details."
        else:
            self.status_msg = "No conflicts detected across managed assignments."


def run_tui(handler: CLIHandler) -> int:
    try:
        return curses.wrapper(lambda stdscr: DHCPManagerTUI(stdscr, handler).run())
    except Exception as e:
        sys.stderr.write(f"Curses TUI execution error: {e}\n")
        sys.stderr.write("Falling back to CLI status view:\n\n")
        return handler.cmd_status()
