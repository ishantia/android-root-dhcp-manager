"""
Application configuration management.
Author: ishantia
"""

from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class Config:
    db_path: str
    log_file: str
    log_level: str
    dry_run: bool
    backup_dir: str
    dnsmasq_hosts_file: str
    dnsmasq_conf_dir: str
    poll_interval_seconds: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfigManager:
    """Manages persistent JSON configuration settings."""

    def __init__(self, config_file: Optional[Path] = None):
        base_dir = Path.home() / ".config" / "android-root-dhcp-manager"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = config_file or (base_dir / "config.json")
        self.config = self.load_config()

    def get_default_config(self) -> Config:
        base_dir = Path.home() / ".config" / "android-root-dhcp-manager"
        return Config(
            db_path=str(base_dir / "dhcp_manager.db"),
            log_file=str(base_dir / "logs" / "app.log"),
            log_level="INFO",
            dry_run=False,
            backup_dir=str(base_dir / "backups"),
            dnsmasq_hosts_file="/data/misc/dhcp/dnsmasq.hosts",
            dnsmasq_conf_dir="/data/misc/dhcp/dnsmasq.d",
            poll_interval_seconds=5,
        )

    def load_config(self) -> Config:
        defaults = self.get_default_config()
        if not self.config_file.exists():
            self.save_config(defaults)
            return defaults

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Config(
                db_path=data.get("db_path", defaults.db_path),
                log_file=data.get("log_file", defaults.log_file),
                log_level=data.get("log_level", defaults.log_level),
                dry_run=bool(data.get("dry_run", defaults.dry_run)),
                backup_dir=data.get("backup_dir", defaults.backup_dir),
                dnsmasq_hosts_file=data.get("dnsmasq_hosts_file", defaults.dnsmasq_hosts_file),
                dnsmasq_conf_dir=data.get("dnsmasq_conf_dir", defaults.dnsmasq_conf_dir),
                poll_interval_seconds=int(data.get("poll_interval_seconds", defaults.poll_interval_seconds)),
            )
        except Exception:
            return defaults

    def save_config(self, config: Optional[Config] = None) -> None:
        cfg = config or self.config
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(cfg.to_dict(), f, indent=2)
        self.config = cfg
