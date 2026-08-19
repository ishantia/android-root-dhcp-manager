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

    def run(self) -> int:
        curses.curs_set(0)
        self.stdscr.nodelay(False)
        self.stdscr.keypad(True)

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)    # Header / Highlight
            curses.init_pair(2, curses.COLOR_GREEN, -1)                  # Status OK
            curses.init_pair(3, curses.COLOR_YELLOW, -1)                 # Warnings
            curses.init_pair(4, curses.COLOR_RED, -1)                    # Errors
            curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)   # Active Tab

        self.refresh_data()

        while True:
            self.draw()
            ch = self.stdscr.getch()

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
        self.assignments = self.handler.db.list_assignments()
        self.net_state = self.handler.discovery.discover_state()
        self.connected_clients = self.handler.scanner.get_connected_clients(self.net_state.tether_interface)

    def move_selection(self, delta: int) -> None:
        max_items = len(self.assignments) if self.active_tab == 0 else len(self.connected_clients)
        if max_items > 0:
            self.selected_index = max(0, min(max_items - 1, self.selected_index + delta))

    def draw(self) -> None:
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()

        if height < 15 or width < 60:
            self.stdscr.addstr(0, 0, "Terminal window too small (min 60x15 required).")
            self.stdscr.refresh()
            return

        # 1. Header Bar
        header = " ANDROID ROOT DHCP MANAGER v1.0.0 "
        tether_str = f"Tethering: [{'ACTIVE' if self.net_state.tethering_active else 'INACTIVE'}]"
        root_str = f"Root: [{'YES' if self.handler.root_executor.check_root() else 'NO'}]"
        title_line = f"{header:<35} {tether_str:<20} {root_str:>15}"
        self.stdscr.attron(curses.color_pair(1) if curses.has_colors() else curses.A_REVERSE)
        self.stdscr.addstr(0, 0, title_line[:width].ljust(width))
        self.stdscr.attroff(curses.color_pair(1) if curses.has_colors() else curses.A_REVERSE)

        # 2. Network Overview Panel
        backend = self.handler._get_active_backend().name
        net_info = (
            f"Interface: {self.net_state.tether_interface or 'None'} | "
            f"Gateway: {self.net_state.gateway_ip or 'None'} | "
            f"Subnet: {self.net_state.subnet_cidr or 'None'} | "
            f"Upstream: {self.net_state.upstream_interface or 'None'} | "
            f"Backend: {backend}"
        )
        self.stdscr.addstr(2, 2, net_info[: width - 4])

        # 3. Tabs (0: Stored Assignments, 1: Connected Clients, 2: Doctor)
        tab0 = "[1] Managed Assignments "
        tab1 = "[2] Connected Clients "
        tab2 = "[3] Doctor Report "

        self.stdscr.addstr(4, 2, "Tabs: ")
        self.draw_tab(4, 8, tab0, self.active_tab == 0)
        self.draw_tab(4, 32, tab1, self.active_tab == 1)
        self.draw_tab(4, 55, tab2, self.active_tab == 2)

        self.stdscr.addstr(5, 0, "-" * width)

        # 4. Content Area
        content_height = height - 8
        if self.active_tab == 0:
            self.draw_assignments_view(6, content_height, width)
        elif self.active_tab == 1:
            self.draw_clients_view(6, content_height, width)
        else:
            self.draw_doctor_view(6, content_height, width)

        # 5. Status / Controls Footer
        self.stdscr.attron(curses.color_pair(1) if curses.has_colors() else curses.A_REVERSE)
        footer = f" {self.status_msg} "
        self.stdscr.addstr(height - 1, 0, footer[:width].ljust(width))
        self.stdscr.attroff(curses.color_pair(1) if curses.has_colors() else curses.A_REVERSE)

        self.stdscr.refresh()

    def draw_tab(self, y: int, x: int, label: str, is_active: bool) -> None:
        if is_active:
            self.stdscr.attron(curses.color_pair(5) if curses.has_colors() else curses.A_BOLD)
            self.stdscr.addstr(y, x, label)
            self.stdscr.attroff(curses.color_pair(5) if curses.has_colors() else curses.A_BOLD)
        else:
            self.stdscr.addstr(y, x, label)

    def draw_assignments_view(self, start_y: int, max_lines: int, width: int) -> None:
        headers = f"{'ID':<4} {'MAC ADDRESS':<18} {'IPV4 ADDRESS':<16} {'STATUS':<8} {'HOSTNAME':<15} {'NOTES'}"
        self.stdscr.addstr(start_y, 2, headers[: width - 4], curses.A_BOLD)

        if not self.assignments:
            self.stdscr.addstr(start_y + 2, 4, "No static IP assignments stored. Press 'A' to add one.")
            return

        for idx, a in enumerate(self.assignments[: max_lines - 2]):
            y = start_y + 1 + idx
            status = "ENABLED" if a.enabled else "DISABLED"
            hostname = (a.hostname[:14] + "…") if len(a.hostname) > 15 else a.hostname
            line = f"{a.id:<4} {a.mac_address:<18} {a.ipv4_address:<16} {status:<8} {hostname:<15} {a.notes}"

            if idx == self.selected_index:
                self.stdscr.attron(curses.A_REVERSE)
                self.stdscr.addstr(y, 2, line[: width - 4].ljust(width - 4))
                self.stdscr.attroff(curses.A_REVERSE)
            else:
                self.stdscr.addstr(y, 2, line[: width - 4])

    def draw_clients_view(self, start_y: int, max_lines: int, width: int) -> None:
        headers = f"{'MAC ADDRESS':<18} {'CURRENT IP':<16} {'IFACE':<8} {'STATE':<10} {'MANAGED'}"
        self.stdscr.addstr(start_y, 2, headers[: width - 4], curses.A_BOLD)

        if not self.connected_clients:
            self.stdscr.addstr(start_y + 2, 4, "No active clients detected on tethering interface.")
            return

        assignments_by_mac = {a.mac_address: a for a in self.assignments}
        for idx, c in enumerate(self.connected_clients[: max_lines - 2]):
            y = start_y + 1 + idx
            managed = f"YES ({assignments_by_mac[c.mac].ipv4_address})" if c.mac in assignments_by_mac else "NO"
            line = f"{c.mac:<18} {c.ip:<16} {c.interface:<8} {c.state:<10} {managed}"

            if idx == self.selected_index:
                self.stdscr.attron(curses.A_REVERSE)
                self.stdscr.addstr(y, 2, line[: width - 4].ljust(width - 4))
                self.stdscr.attroff(curses.A_REVERSE)
            else:
                self.stdscr.addstr(y, 2, line[: width - 4])

    def draw_doctor_view(self, start_y: int, max_lines: int, width: int) -> None:
        self.stdscr.addstr(start_y, 2, "Running Quick Environment Diagnostic...", curses.A_BOLD)
        doc = self.handler.cmd_status()
        self.stdscr.addstr(start_y + 2, 2, "Press 'L' or switch tabs to navigate.")

    def prompt_input(self, title: str, fields: List[str]) -> Optional[List[str]]:
        curses.echo()
        curses.curs_set(1)
        height, width = self.stdscr.getmaxyx()
        win = curses.newwin(len(fields) + 6, width - 10, 4, 5)
        win.box()
        win.addstr(1, 2, f"=== {title} ===", curses.A_BOLD)

        results: List[str] = []
        for idx, field_name in enumerate(fields):
            win.addstr(idx + 3, 2, f"{field_name}: ")
            win.refresh()
            inp = win.getstr(idx + 3, len(field_name) + 4, 40).decode("utf-8").strip()
            results.append(inp)

        curses.noecho()
        curses.curs_set(0)
        return results

    def action_add(self) -> None:
        res = self.prompt_input("Add Static IP Assignment", ["MAC Address", "IPv4 Address", "Hostname (optional)"])
        if res and res[0] and res[1]:
            mac, ip, host = res[0], res[1], res[2] if len(res) > 2 else ""
            exit_code = self.handler.cmd_add(mac=mac, ip=ip, hostname=host)
            if exit_code == 0:
                self.status_msg = f"Successfully added assignment {mac} -> {ip}"
            else:
                self.status_msg = "Error adding assignment. Check conflicts."
            self.refresh_data()

    def action_edit(self) -> None:
        if not self.assignments or self.selected_index >= len(self.assignments):
            self.status_msg = "No assignment selected to edit."
            return

        asgn = self.assignments[self.selected_index]
        res = self.prompt_input(f"Edit Assignment #{asgn.id}", [f"IPv4 Address ({asgn.ipv4_address})", f"Hostname ({asgn.hostname})"])
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
            self.status_msg = "Successfully applied and verified static IP configuration!"
        else:
            self.status_msg = "Apply completed with warnings or errors. Check logs."

    def action_conflicts(self) -> None:
        self.status_msg = "Checking network conflicts..."
        self.handler.cmd_conflicts()
        self.status_msg = "Conflict check complete. View console output for details."


def run_tui(handler: CLIHandler) -> int:
    try:
        return curses.wrapper(lambda stdscr: DHCPManagerTUI(stdscr, handler).run())
    except Exception as e:
        sys.stderr.write(f"Curses TUI execution error: {e}\n")
        sys.stderr.write("Falling back to CLI status view:\n\n")
        return handler.cmd_status()
