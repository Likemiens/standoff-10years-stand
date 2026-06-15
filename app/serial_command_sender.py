from __future__ import annotations

import logging
import time
from typing import Any

from app.serial_client import find_serial_port


class SerialCommandSender:
    def __init__(self, config: dict[str, Any], logger: logging.Logger, name: str = "serial_command"):
        self.config = config
        self.logger = logger
        self.name = name
        self.enabled = bool(config.get("enabled", True))
        self.configured_port = str(config.get("port", "auto"))
        self.baud_rate = int(config.get("baudRate", 9600))
        self.line_ending = str(config.get("lineEnding", "\n"))
        self.open_delay_ms = int(config.get("openDelayMs", 1500))
        self._serial = None
        self.current_port = ""

    def start(self) -> None:
        if not self.enabled:
            self.logger.info("serial_command_disabled | name=%s", self.name)
            return
        self._ensure_open()

    def stop(self) -> None:
        if self._serial is None:
            return
        try:
            self._serial.close()
        except Exception:
            pass
        finally:
            self._serial = None
            self.logger.info("serial_command_disconnected | name=%s | port=%s", self.name, self.current_port or "-")

    def write_line(self, line: str) -> bool:
        if not self._ensure_open():
            return False
        payload = f"{line}{self.line_ending}".encode("utf-8")
        try:
            self._serial.write(payload)
            self._serial.flush()
            self.logger.info("serial_command_write | name=%s | port=%s | line=%s", self.name, self.current_port, line)
            return True
        except Exception as exc:
            self.logger.error("serial_command_error | name=%s | port=%s | error=%s", self.name, self.current_port or "-", exc)
            self.stop()
            return False

    def _ensure_open(self) -> bool:
        if self._serial is not None and getattr(self._serial, "is_open", False):
            return True

        try:
            import serial
        except ImportError:
            self.logger.error("serial_command_error | name=%s | pyserial is not installed", self.name)
            return False

        port = self.configured_port
        if port.lower() == "auto":
            port = find_serial_port(self.logger) or ""
        if not port:
            self.logger.error("serial_command_error | name=%s | COM port not found", self.name)
            return False

        try:
            self._serial = serial.Serial(port, self.baud_rate, timeout=0.2, write_timeout=1)
            self.current_port = port
            if self.open_delay_ms > 0:
                time.sleep(self.open_delay_ms / 1000)
            self.logger.info("serial_command_connected | name=%s | port=%s | baud=%s", self.name, port, self.baud_rate)
            return True
        except Exception as exc:
            self._serial = None
            self.logger.error("serial_command_error | name=%s | port=%s | error=%s", self.name, port, exc)
            return False
