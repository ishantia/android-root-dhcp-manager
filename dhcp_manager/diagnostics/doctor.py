"""
System Doctor and Self-Check Diagnostic Engine.
Checks Termux environment, root status, binaries, interfaces, tethering, DHCP backend, and config directory.
Author: ishantia
"""

from dataclasses import dataclass, field
import os
import platform
import shutil
from typing import List, Dict, Any, Optional
from dhcp_manager.core.models import NetworkState
from dhcp_manager.root.executor import RootExecutor
from dhcp_manager.network.discovery import NetworkDiscovery
from dhcp_manager.dhcp.dnsmasq import DnsmasqBackend
from dhcp_manager.dhcp.android import AndroidTetheringBackend


@dataclass
class CheckResult:
    name: str
    passed: bool
    status: str
    details: str = ""
    remediation: str = ""


@dataclass
class DiagnosticReport:
    is_fully_supported: bool
    checks: List[CheckResult] = field(default_factory=list)
    system_info: Dict[str, Any] = field(default_factory=dict)
    network_state: Optional[NetworkState] = None


class SystemDoctor:
    """Performs deep diagnostic inspection of the Android environment."""

    def __init__(self, root_executor: RootExecutor, discovery: NetworkDiscovery):
        self.executor = root_executor
        self.discovery = discovery

    def run_diagnostics(self) -> DiagnosticReport:
        checks: List[CheckResult] = []

        # 1. Termux environment check
        is_termux = "TERMUX_VERSION" in os.environ or os.path.exists("/data/data/com.termux")
        checks.append(
            CheckResult(
                name="Termux Environment",
                passed=is_termux,
                status="OK (Termux detected)" if is_termux else "WARNING (Not running in standard Termux)",
                details=f"TERMUX_VERSION={os.environ.get('TERMUX_VERSION', 'N/A')}",
                remediation="Recommended to run inside Termux terminal app on Android.",
            )
        )

        # 2. Root Access check
        has_root = self.executor.check_root(force_recheck=True)
        checks.append(
            CheckResult(
                name="Root Access (su)",
                passed=has_root,
                status="OK (Root privileges available)" if has_root else "FAIL (Root access unavailable)",
                details=f"su binary path: {self.executor._su_path}",
                remediation="Ensure device is rooted (Magisk/KernelSU/APatch) and grant superuser permission to Termux.",
            )
        )

        # 3. Command binaries check
        required_cmds = ["ip", "cat", "ps", "sh"]
        optional_cmds = ["dnsmasq", "iptables", "killall"]
        missing_required = [cmd for cmd in required_cmds if not shutil.which(cmd) and not self._has_root_cmd(cmd)]

        cmds_passed = len(missing_required) == 0
        checks.append(
            CheckResult(
                name="System Binary Tools",
                passed=cmds_passed,
                status="OK" if cmds_passed else f"FAIL (Missing: {', '.join(missing_required)})",
                details=f"Required present: {set(required_cmds) - set(missing_required)}",
                remediation="Install net-tools / iproute2 / toybox in Termux via 'pkg install iproute2'.",
            )
        )

        # 4. Network Discovery
        net_state = self.discovery.discover_state()
        tether_ok = net_state.tethering_active
        checks.append(
            CheckResult(
                name="Active Tethering Interface",
                passed=tether_ok,
                status=f"OK ({net_state.tether_interface})" if tether_ok else "INFO (Hotspot not currently active)",
                details=(
                    f"Interface: {net_state.tether_interface or 'None'}, "
                    f"Gateway: {net_state.gateway_ip or 'None'}, "
                    f"Subnet: {net_state.subnet_cidr or 'None'}"
                ),
                remediation="Turn on Wi-Fi Hotspot / Tethering on your Android device.",
            )
        )

        # 5. Upstream Interface Discovery
        upstream_ok = net_state.upstream_interface is not None
        checks.append(
            CheckResult(
                name="Upstream Network Interface",
                passed=upstream_ok,
                status=f"OK ({net_state.upstream_interface})" if upstream_ok else "INFO (No active default upstream interface)",
                details=f"Upstream: {net_state.upstream_interface or 'Disconnected/Offline'}",
                remediation="Ensure Wi-Fi or Cellular Data or VPN is connected.",
            )
        )

        # 6. DHCP Server / Backend Inspection
        dnsmasq_backend = DnsmasqBackend(self.executor)
        has_dnsmasq = dnsmasq_backend.detect_active()

        android_backend = AndroidTetheringBackend(self.executor)

        active_backend_name = "dnsmasq" if has_dnsmasq else android_backend.name
        net_state.dhcp_backend_type = active_backend_name
        if has_dnsmasq:
            net_state.dnsmasq_pid = dnsmasq_backend.pid
            net_state.dnsmasq_cmd = dnsmasq_backend.cmdline
            net_state.dnsmasq_lease_file = dnsmasq_backend.lease_file

        checks.append(
            CheckResult(
                name="DHCP Backend Implementation",
                passed=True,
                status=f"OK (Backend: {active_backend_name})",
                details=(
                    f"dnsmasq present: {has_dnsmasq} (PID: {dnsmasq_backend.pid or 'N/A'}), "
                    f"lease file: {dnsmasq_backend.lease_file or 'N/A'}"
                ),
                remediation="",
            )
        )

        # 7. Config Directory Writeability
        config_dir = os.path.expanduser("~/.config/android-root-dhcp-manager")
        try:
            os.makedirs(config_dir, exist_ok=True)
            test_file = os.path.join(config_dir, ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            config_write_ok = True
        except Exception:
            config_write_ok = False

        checks.append(
            CheckResult(
                name="Config Storage Directory",
                passed=config_write_ok,
                status="OK" if config_write_ok else "FAIL (Config directory unwritable)",
                details=f"Path: {config_dir}",
                remediation="Ensure storage permissions are granted in Termux.",
            )
        )

        sys_info = {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
        }

        all_passed = all(c.passed for c in checks if c.name not in ("Active Tethering Interface", "Upstream Network Interface"))

        return DiagnosticReport(
            is_fully_supported=all_passed,
            checks=checks,
            system_info=sys_info,
            network_state=net_state,
        )

    def _has_root_cmd(self, cmd: str) -> bool:
        res = self.executor.execute(["which", cmd], use_root=True)
        return res.success and bool(res.stdout)
