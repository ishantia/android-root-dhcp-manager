"""
Main Entry point for Android Root DHCP Manager CLI.
Author: ishantia
"""

import argparse
import sys
from dhcp_manager.cli.commands import CLIHandler


__version__ = "1.0.0"


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="dhcp-manager",
        description="Android Root DHCP / IP Manager TUI & CLI for Termux",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s v{__version__}"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without modifying system network configuration",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available Commands")

    # status
    subparsers.add_parser("status", help="Show active tethering and network status")

    # list
    subparsers.add_parser("list", help="List stored static IP assignments")

    # add
    add_parser = subparsers.add_parser("add", help="Add new static IP assignment")
    add_parser.add_argument("--mac", required=True, help="Client MAC address (e.g. 28:3F:69:64:69:73)")
    add_parser.add_argument("--ip", required=True, help="Static IPv4 address (e.g. 10.189.149.16)")
    add_parser.add_argument("--hostname", default="", help="Optional hostname label")
    add_parser.add_argument("--notes", default="", help="Optional notes")
    add_parser.add_argument("--disabled", action="store_true", help="Add assignment in disabled state")

    # remove
    rm_parser = subparsers.add_parser("remove", help="Remove assignment by MAC or ID")
    rm_parser.add_argument("identifier", help="MAC address or assignment ID")

    # set-ip
    setip_parser = subparsers.add_parser("set-ip", help="Set IP address for a given MAC")
    setip_parser.add_argument("mac", help="Client MAC address")
    setip_parser.add_argument("ip", help="New IPv4 address")

    # enable / disable
    en_parser = subparsers.add_parser("enable", help="Enable assignment by MAC or ID")
    en_parser.add_argument("identifier", help="MAC address or assignment ID")

    dis_parser = subparsers.add_parser("disable", help="Disable assignment by MAC or ID")
    dis_parser.add_argument("identifier", help="MAC address or assignment ID")

    # inspect
    ins_parser = subparsers.add_parser("inspect", help="Inspect details of an assignment")
    ins_parser.add_argument("identifier", help="MAC address or assignment ID")

    # scan
    subparsers.add_parser("scan", help="Scan active connected clients on tethering network")

    # conflicts
    subparsers.add_parser("conflicts", help="Check for IP & MAC conflicts across database and network")

    # apply
    apply_parser = subparsers.add_parser("apply", help="Apply stored assignments to active network/DHCP server")
    apply_parser.add_argument("--dry-run", action="store_true", help="Perform dry-run simulation")

    # reload
    subparsers.add_parser("reload", help="Reload active DHCP server configuration")

    # backup
    bak_parser = subparsers.add_parser("backup", help="Export assignments to backup JSON file")
    bak_parser.add_argument("--output", "-o", help="Target output file path")

    # restore
    res_parser = subparsers.add_parser("restore", help="Import assignments from JSON file")
    res_parser.add_argument("input", help="Source JSON file path")
    res_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing MAC assignments")

    # doctor
    subparsers.add_parser("doctor", help="Run system diagnostics and environment check")

    # tui
    subparsers.add_parser("tui", help="Launch interactive terminal user interface")

    args = parser.parse_args()

    # Default command: launch TUI if interactive terminal and no subcommands, else show help
    if not args.command:
        if sys.stdin.isatty():
            args.command = "tui"
        else:
            parser.print_help()
            return 0

    handler = CLIHandler(dry_run=getattr(args, "dry_run", False))

    if args.command == "status":
        return handler.cmd_status()
    elif args.command == "list":
        return handler.cmd_list()
    elif args.command == "add":
        return handler.cmd_add(
            mac=args.mac,
            ip=args.ip,
            hostname=args.hostname,
            notes=args.notes,
            disabled=args.disabled,
        )
    elif args.command == "remove":
        return handler.cmd_remove(args.identifier)
    elif args.command == "set-ip":
        return handler.cmd_set_ip(args.mac, args.ip)
    elif args.command == "enable":
        return handler.cmd_enable_disable(args.identifier, enable=True)
    elif args.command == "disable":
        return handler.cmd_enable_disable(args.identifier, enable=False)
    elif args.command == "inspect":
        return handler.cmd_inspect(args.identifier)
    elif args.command == "scan":
        return handler.cmd_scan()
    elif args.command == "conflicts":
        return handler.cmd_conflicts()
    elif args.command == "apply":
        return handler.cmd_apply(dry_run=args.dry_run or handler.config.dry_run)
    elif args.command == "reload":
        return handler.cmd_reload()
    elif args.command == "backup":
        return handler.cmd_backup(args.output)
    elif args.command == "restore":
        return handler.cmd_restore(args.input, overwrite=args.overwrite)
    elif args.command == "doctor":
        return handler.cmd_doctor()
    elif args.command == "tui":
        try:
            from dhcp_manager.tui.app import run_tui
            return run_tui(handler)
        except Exception as e:
            print(f"Failed to start TUI: {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
