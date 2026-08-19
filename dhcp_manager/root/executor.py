"""
Root Executor Module.
Provides secure privileged execution via 'su', command escaping, timeout control, and dry-run mode.
"""

from dataclasses import dataclass
import os
import shlex
import shutil
import subprocess
import time
from typing import List, Optional, Union
from dhcp_manager.logging.logger import get_logger, Subsystem


logger = get_logger(Subsystem.ROOT)


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    command_str: str
    duration_ms: float

    @property
    def success(self) -> bool:
        return self.exit_code == 0


class RootExecutor:
    """Safely handles execution of root commands on Android devices via 'su'."""

    def __init__(self, dry_run: bool = False, su_binary: Optional[str] = None):
        self.dry_run = dry_run
        self._su_path = su_binary or self._find_su_binary()
        self._is_root_available: Optional[bool] = None

    def _find_su_binary(self) -> str:
        paths = [
            "/system/bin/su",
            "/system/xbin/su",
            "/sbin/su",
            "/system/sd/xbin/su",
            "/vendor/bin/su",
            "su",
        ]
        for p in paths:
            if shutil.which(p) or os.path.exists(p):
                return p
        return "su"

    def check_root(self, force_recheck: bool = False) -> bool:
        if self._is_root_available is not None and not force_recheck:
            return self._is_root_available

        # Check if already running as root UID 0
        try:
            if hasattr(os, "getuid") and os.getuid() == 0:
                self._is_root_available = True
                return True
        except Exception:
            pass

        # Try executing 'id' via su
        res = self.execute(["id"], use_root=True, timeout=5)
        if res.success and ("uid=0" in res.stdout or "root" in res.stdout):
            self._is_root_available = True
            return True

        self._is_root_available = False
        return False

    def execute(
        self,
        command: Union[List[str], str],
        timeout: int = 15,
        use_root: bool = True,
    ) -> CommandResult:
        """
        Executes a command (optionally with root).
        Arguments are safely quoted to avoid command injection.
        """
        if isinstance(command, list):
            escaped_args = [shlex.quote(str(arg)) for arg in command]
            raw_cmd_str = " ".join(escaped_args)
        else:
            raw_cmd_str = command.strip()

        if use_root and not (hasattr(os, "getuid") and os.getuid() == 0):
            # Format su command safely
            full_cmd = [self._su_path, "-c", raw_cmd_str]
        else:
            if isinstance(command, list):
                full_cmd = command
            else:
                full_cmd = ["sh", "-c", raw_cmd_str]

        display_cmd = raw_cmd_str if use_root else " ".join(full_cmd) if isinstance(full_cmd, list) else full_cmd

        if self.dry_run and use_root:
            logger.info(f"[DRY-RUN ROOT CMD]: {raw_cmd_str}")
            return CommandResult(
                exit_code=0,
                stdout=f"[DRY-RUN] Executed: {raw_cmd_str}",
                stderr="",
                command_str=raw_cmd_str,
                duration_ms=0.0,
            )

        start_time = time.time()
        try:
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate(timeout=timeout)
            duration = (time.time() - start_time) * 1000.0

            result = CommandResult(
                exit_code=process.returncode,
                stdout=stdout.strip() if stdout else "",
                stderr=stderr.strip() if stderr else "",
                command_str=display_cmd,
                duration_ms=duration,
            )

            if not result.success:
                logger.warning(
                    f"Command failed (code {result.exit_code}): '{display_cmd}' | Stderr: {result.stderr}"
                )
            else:
                logger.debug(f"Executed ({result.duration_ms:.1f}ms): '{display_cmd}'")

            return result

        except subprocess.TimeoutExpired:
            process.kill()
            duration = (time.time() - start_time) * 1000.0
            msg = f"Command timed out after {timeout}s: '{display_cmd}'"
            logger.error(msg)
            return CommandResult(
                exit_code=124,
                stdout="",
                stderr=msg,
                command_str=display_cmd,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000.0
            msg = f"Failed to execute command '{display_cmd}': {e}"
            logger.error(msg)
            return CommandResult(
                exit_code=1,
                stdout="",
                stderr=msg,
                command_str=display_cmd,
                duration_ms=duration,
            )
