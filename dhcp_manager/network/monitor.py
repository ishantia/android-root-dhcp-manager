"""
Network state monitor for continuous background tracking of tethering and clients.
Author: ishantia
"""

import threading
import time
from typing import Callable, Optional, Dict, Set
from dhcp_manager.core.models import NetworkState, NeighborEntry
from dhcp_manager.network.discovery import NetworkDiscovery
from dhcp_manager.network.neighbors import NeighborScanner
from dhcp_manager.logging.logger import get_logger, Subsystem


logger = get_logger(Subsystem.NETWORK)


class NetworkMonitor:
    """Monitors tethering interface and connected clients asynchronously."""

    def __init__(
        self,
        discovery: NetworkDiscovery,
        scanner: NeighborScanner,
        poll_interval: int = 5,
    ):
        self.discovery = discovery
        self.scanner = scanner
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_state: Optional[NetworkState] = None
        self._known_macs: Set[str] = set()

        self.on_client_connect: Optional[Callable[[NeighborEntry], None]] = None
        self.on_client_disconnect: Optional[Callable[[str], None]] = None
        self.on_tether_change: Optional[Callable[[NetworkState], None]] = None

    def poll_now(self) -> NetworkState:
        state = self.discovery.discover_state()
        if state.tether_interface:
            clients = self.scanner.get_connected_clients(state.tether_interface)
            state.connected_clients = clients
        else:
            state.connected_clients = []

        self._check_diff(state)
        self._last_state = state
        return state

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"NetworkMonitor started with {self.poll_interval}s interval.")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("NetworkMonitor stopped.")

    def _run_loop(self) -> None:
        while self._running:
            try:
                self.poll_now()
            except Exception as e:
                logger.error(f"Error in NetworkMonitor loop: {e}")
            time.sleep(self.poll_interval)

    def _check_diff(self, new_state: NetworkState) -> None:
        if self._last_state is None:
            if new_state.tethering_active and self.on_tether_change:
                self.on_tether_change(new_state)
            self._known_macs = {c.mac for c in new_state.connected_clients}
            return

        if (
            self._last_state.tethering_active != new_state.tethering_active
            or self._last_state.tether_interface != new_state.tether_interface
        ):
            logger.info(f"Tethering state changed: Active={new_state.tethering_active}, Iface={new_state.tether_interface}")
            if self.on_tether_change:
                self.on_tether_change(new_state)

        current_macs = {c.mac: c for c in new_state.connected_clients}

        # Check newly connected
        for mac, client in current_macs.items():
            if mac not in self._known_macs:
                logger.info(f"Client connected: {mac} ({client.ip})")
                if self.on_client_connect:
                    self.on_client_connect(client)

        # Check disconnected
        for mac in self._known_macs:
            if mac not in current_macs:
                logger.info(f"Client disconnected: {mac}")
                if self.on_client_disconnect:
                    self.on_client_disconnect(mac)

        self._known_macs = set(current_macs.keys())
