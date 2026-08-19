# Android Root DHCP / IP Manager

A production-quality, terminal-based (**TUI / CLI**) Android Root DHCP and IP address manager designed specifically for **Termux on rooted Android devices**.

This application allows Android device owners to persistently bind static IPv4 addresses to client devices connected to the Android Wi-Fi hotspot by MAC address (e.g. `28:3F:69:64:69:73` -> `10.189.149.16`).

---

## Features

- **MAC-to-IPv4 Static Bindings**: Persistently map MAC addresses to specific IPv4 addresses within the tethering subnet.
- **Dynamic Environment Discovery**: Automatically detects active tethering interface (`ap0`, `wlan1`, `swlan0`, etc.), gateway IP, subnet CIDR, default upstream interface (`tun0` for VPNs, `rmnet0`, `wlan0`), and DHCP server implementation without hardcoded parameters.
- **Multi-Source Client Discovery**: Scans connected devices using `ip neigh`, `/proc/net/arp`, and DHCP lease files.
- **Capability-Driven DHCP Backends**:
  - **Dnsmasq Backend**: Detects running `dnsmasq`, parses command line arguments and lease files, and injects static hosts via `dnsmasq.conf` fragments or `dnsmasq.hosts`.
  - **Android Netd / APEX Backend**: Integrates with modern Android tethering stacks (`enableLegacyDhcpServer: false`) via kernel ARP neighbor bindings and routing rules.
  - **Generic Linux Backend**: Fallback iproute2 implementation.
- **Interactive TUI Dashboard**: Full terminal user interface built with Python `curses` featuring tabbed views, assignment tables, client scan panels, interactive forms, and keyboard shortcuts.
- **Conflict Detection Engine**: Checks for IP collisions, out-of-subnet IPs, gateway collisions, reserved addresses, active ARP collisions, and stored database conflicts before applying changes.
- **Dry-Run Mode**: Inspect generated configurations and commands (`--dry-run`) without modifying system state.
- **Diagnostics (`dhcp-manager doctor`)**: Comprehensive environment auditor checking Termux, root access, binary utilities, interface states, and configuration storage.
- **Portable Import/Export**: Human-readable JSON backup and restore with pre-validation safety checks.

---

## Requirements

1. **Android Device**: Rooted via Magisk, KernelSU, APatch, or standard `su`.
2. **Termux**: Installed on the Android device.
3. **Python**: Python 3.8+ installed inside Termux (`pkg install python`).
4. **Networking Utilities**: `iproute2` / `toybox` (available in Termux via `pkg install iproute2`).

---

## Installation in Termux

Execute the following commands in your Termux terminal on the rooted Android device:

```bash
# 1. Update Termux packages and install Python & git
pkg update && pkg install -y python git iproute2

# 2. Clone the repository
git clone https://github.com/ishantia/android-root-dhcp-manager.git
cd android-root-dhcp-manager

# 3. Install the package
pip install .

# 4. Grant root permission to Termux (when prompted by Magisk/KernelSU)
su -c id
```

---

## Usage

### Interactive TUI Dashboard

Launch the TUI by running:

```bash
dhcp-manager
# or
python -m dhcp_manager tui
```

#### TUI Keyboard Shortcuts:
- **`[1]` / `[2]` / `[3]` or `Tab`**: Switch tabs (Assignments / Connected Clients / Doctor Report)
- **`A`**: Add new static assignment
- **`E`**: Edit selected assignment
- **`D`**: Delete selected assignment
- **`P`**: Apply static configuration to active network
- **`C`**: Check network conflicts
- **`R`**: Refresh status & client scan
- **`Q`**: Quit TUI

---

### Command Line Interface (CLI)

#### Check Network Status
```bash
dhcp-manager status
```

#### Run Diagnostics / Environment Doctor
```bash
dhcp-manager doctor
```

#### List Stored Static Assignments
```bash
dhcp-manager list
```

#### Add Static IP Assignment
```bash
dhcp-manager add --mac 28:3F:69:64:69:73 --ip 10.189.149.16 --hostname MyLaptop
```

#### Quick Set IP for MAC
```bash
dhcp-manager set-ip 28:3F:69:64:69:73 10.189.149.16
```

#### Inspect Assignment Details & Active Connection State
```bash
dhcp-manager inspect 28:3F:69:64:69:73
```

#### Enable / Disable Assignment
```bash
dhcp-manager enable 28:3F:69:64:69:73
dhcp-manager disable 28:3F:69:64:69:73
```

#### Remove Assignment
```bash
dhcp-manager remove 28:3F:69:64:69:73
```

#### Scan Active Connected Clients
```bash
dhcp-manager scan
```

#### Run Conflict Detector
```bash
dhcp-manager conflicts
```

#### Apply Static IP Assignments to Active Network
```bash
# Dry-run simulation (safe testing)
dhcp-manager apply --dry-run

# Live apply with post-verification
dhcp-manager apply
```

#### Reload DHCP Server
```bash
dhcp-manager reload
```

#### Export / Import Backup
```bash
# Backup to JSON file
dhcp-manager backup -o my_assignments.json

# Restore from JSON file
dhcp-manager restore my_assignments.json --overwrite
```

---

## Configuration & Storage Directory

All persistent state is stored in standard XDG user configuration paths:

- **Database**: `~/.config/android-root-dhcp-manager/dhcp_manager.db` (SQLite with schema versioning)
- **Config**: `~/.config/android-root-dhcp-manager/config.json`
- **Logs**: `~/.config/android-root-dhcp-manager/logs/app.log`
- **Backups**: `~/.config/android-root-dhcp-manager/backups/`

---

## Architecture Overview

```
                          ┌───────────────────────────┐
                          │  CLI & TUI User Interface │
                          └─────────────┬─────────────┘
                                        │
                          ┌─────────────▼─────────────┐
                          │    CLI Commands Handler   │
                          └─────────────┬─────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │                            │                            │
┌──────────▼──────────┐      ┌──────────▼──────────┐      ┌──────────▼──────────┐
│ SQLite Database &   │      │ Conflict Detector & │      │ Network Discovery & │
│ Schema Versioning   │      │ MAC/IPv4 Validator  │      │ Neighbor Scanner    │
└─────────────────────┘      └─────────────────────┘      └──────────┬──────────┘
                                                                     │
                                                          ┌──────────▼──────────┐
                                                          │   NetworkBackend    │
                                                          │ (dnsmasq/netd/gen)  │
                                                          └──────────┬──────────┘
                                                                     │
                                                          ┌──────────▼──────────┐
                                                          │ Root Execution Layer│
                                                          │   (su / escaping)   │
                                                          └─────────────────────┘
```

---

## Security Notes

- Executed commands use strict argument escaping (`shlex.quote`) to prevent shell injection attacks.
- Privileged operations require explicit user approval (`su`).
- System files are modified only when required, and non-destructive runtime network mechanisms are preferred wherever possible.

---

## License

MIT License
