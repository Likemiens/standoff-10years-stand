from __future__ import annotations

import copy
import logging
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from app.constants import VALID_DUAL_DIGIT_PATTERN
from app.dual_digit_parser import parse_dual_digit_value
from app.serial_client import SerialClient, find_serial_ports


class DualDigitSerialClient(QObject):
    rawLineReceived = Signal(str)
    validValueReceived = Signal(str)
    invalidLineReceived = Signal(str)
    statusChanged = Signal(bool, str)
    errorOccurred = Signal(str)

    def __init__(self, config: dict[str, Any], logger: logging.Logger):
        super().__init__()
        self.config = config
        self.logger = logger
        self.enabled = bool(config.get("enabled", True))
        self.dual_config = config.get("dual", {})
        self.reconnect_interval_ms = int(config.get("reconnectIntervalMs", 2000))
        self.tens_client: SerialClient | None = None
        self.ones_client: SerialClient | None = None
        self.tens_digit = ""
        self.ones_digit = ""
        self.tens_connected = False
        self.ones_connected = False
        self.tens_port = ""
        self.ones_port = ""
        self._stopping = False

        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._start_clients)

    def start(self) -> None:
        if not self.enabled:
            self.statusChanged.emit(False, "dual serial disabled")
            self.logger.info("serial_disabled | mode=dual_digit")
            return
        self._start_clients()

    def stop(self) -> None:
        self._stopping = True
        self._retry_timer.stop()
        if self.tens_client is not None:
            self.tens_client.stop()
        if self.ones_client is not None:
            self.ones_client.stop()

    def write_line(self, line: str) -> bool:
        target = str(self.dual_config.get("ledTarget", "tens")).lower()
        if target == "both":
            left = self.tens_client.write_line(line) if self.tens_client else False
            right = self.ones_client.write_line(line) if self.ones_client else False
            return left or right
        if target == "ones":
            return self.ones_client.write_line(line) if self.ones_client else False
        return self.tens_client.write_line(line) if self.tens_client else False

    def _start_clients(self) -> None:
        if self._stopping:
            return
        if self.tens_client is not None or self.ones_client is not None:
            return

        ports = self._resolve_ports()
        tens_port = ports.get("tens", "")
        ones_port = ports.get("ones", "")

        if not tens_port or not ones_port:
            self.errorOccurred.emit("Dual Arduino ports not found")
            self.logger.error("serial_error | mode=dual_digit | ports not found | tens=%s | ones=%s", tens_port or "-", ones_port or "-")
            self._emit_status()
            self._schedule_retry()
            return

        self.tens_port = tens_port
        self.ones_port = ones_port
        self.tens_client = self._create_digit_client("tens", tens_port)
        self.ones_client = self._create_digit_client("ones", ones_port)
        self.tens_client.start()
        self.ones_client.start()

    def _resolve_ports(self) -> dict[str, str]:
        tens_port = str(self.dual_config.get("tensPort", "auto"))
        ones_port = str(self.dual_config.get("onesPort", "auto"))

        auto_ports = find_serial_ports(8, self.logger)

        def pick_auto(exclude: set[str]) -> str:
            for port in auto_ports:
                if port not in exclude:
                    return port
            return ""

        selected: dict[str, str] = {"tens": "", "ones": ""}

        if tens_port.lower() != "auto":
            selected["tens"] = tens_port
        if ones_port.lower() != "auto":
            selected["ones"] = ones_port

        if tens_port.lower() == "auto":
            selected["tens"] = pick_auto({selected["ones"]} if selected["ones"] else set())
        if ones_port.lower() == "auto":
            selected["ones"] = pick_auto({selected["tens"]} if selected["tens"] else set())

        if selected["tens"] == selected["ones"]:
            selected["ones"] = ""

        self.logger.info("dual_serial_ports | tens=%s | ones=%s", selected["tens"] or "-", selected["ones"] or "-")
        return selected

    def _create_digit_client(self, role: str, port: str) -> SerialClient:
        client_config = copy.deepcopy(self.config)
        client_config["port"] = port
        client = SerialClient(
            client_config,
            self.logger,
            port=port,
            value_pattern=VALID_DUAL_DIGIT_PATTERN,
            name=f"arduino_{role}",
        )
        client.rawLineReceived.connect(lambda raw, selected=role: self.rawLineReceived.emit(f"{selected}:{raw}"))
        client.invalidLineReceived.connect(lambda raw, selected=role: self._handle_invalid_digit(selected, raw))
        client.validValueReceived.connect(lambda digit, selected=role: self._handle_digit(selected, digit))
        client.errorOccurred.connect(lambda message, selected=role: self._handle_error(selected, message))
        client.statusChanged.connect(lambda connected, port_name, selected=role: self._handle_status(selected, connected, port_name))
        return client

    def _handle_digit(self, role: str, raw_value: str) -> None:
        parsed = parse_dual_digit_value(raw_value, fallback_role=role)
        if parsed is None:
            self._handle_invalid_digit(role, raw_value)
            return

        effective_role, digit = parsed
        if effective_role != role:
            self.logger.info("dual_digit_role_override | port_role=%s | payload_role=%s | raw=%s", role, effective_role, raw_value)

        if effective_role == "tens":
            if self.tens_digit == digit:
                return
            self.tens_digit = digit
        else:
            if self.ones_digit == digit:
                return
            self.ones_digit = digit

        self.logger.info(
            "dual_digit | role=%s | digit=%s | tens=%s | ones=%s",
            effective_role,
            digit,
            self.tens_digit or "-",
            self.ones_digit or "-",
        )

        if self.tens_digit and self.ones_digit:
            combined = f"{self.tens_digit}{self.ones_digit}"
            self.rawLineReceived.emit(f"combined:{combined}")
            self.validValueReceived.emit(combined)

    def _handle_invalid_digit(self, role: str, raw: str) -> None:
        message = f"{role}:{raw}"
        self.invalidLineReceived.emit(message)
        self.logger.warning("invalid_digit | role=%s | raw=%r", role, raw)

    def _handle_error(self, role: str, message: str) -> None:
        self.errorOccurred.emit(f"{role}: {message}")

    def _handle_status(self, role: str, connected: bool, port: str) -> None:
        if role == "tens":
            self.tens_connected = connected
            if port:
                self.tens_port = port
        else:
            self.ones_connected = connected
            if port:
                self.ones_port = port
        self._emit_status()

    def _emit_status(self) -> None:
        connected = self.tens_connected and self.ones_connected
        summary = f"tens={self.tens_port or '-'}:{'connected' if self.tens_connected else 'disconnected'}; ones={self.ones_port or '-'}:{'connected' if self.ones_connected else 'disconnected'}"
        self.statusChanged.emit(connected, summary)

    def _schedule_retry(self) -> None:
        if self.reconnect_interval_ms <= 0 or self._retry_timer.isActive():
            return
        self._retry_timer.start(self.reconnect_interval_ms)
