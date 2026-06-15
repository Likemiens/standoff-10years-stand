from __future__ import annotations

import logging
from typing import Any, Protocol


class SerialSender(Protocol):
    def write_line(self, line: str) -> bool:
        ...


class LedController:
    def __init__(self, config: dict[str, Any], logger: logging.Logger, serial_sender: SerialSender | None = None):
        self.config = config
        self.logger = logger
        self.serial_sender = serial_sender
        self.enabled = bool(config.get("enabled", False))
        self.mode = str(config.get("mode", "serial"))
        self.status = "disabled" if not self.enabled else "ready"
        self.last_command = ""
        self.last_error = ""

    def set_serial_sender(self, serial_sender: SerialSender | None) -> None:
        self.serial_sender = serial_sender

    def send_run(self) -> bool:
        return self.send("run")

    def send_off(self) -> bool:
        return self.send("off")

    def send_idle(self) -> bool:
        return self.send("idle")

    def send_error(self) -> bool:
        return self.send("error")

    def send_out_of_range(self) -> bool:
        return self.send("outOfRange")

    def send(self, command_name: str) -> bool:
        key = f"{command_name}Command"
        command = str(self.config.get(key, "")).strip()
        self.last_command = command or command_name

        if not self.enabled:
            self.status = "disabled"
            self.logger.info("led_skipped | reason=disabled | command=%s", self.last_command)
            return True

        if not command:
            return self._fail(f"LED command is empty: {command_name}")

        if self.mode != "serial":
            return self._fail(f"Unsupported LED mode: {self.mode}")

        if self.serial_sender is None:
            return self._fail(f"Cannot send LED command without serial sender: {command}")

        if not self.serial_sender.write_line(command):
            return self._fail(f"Cannot send LED command: {command}")

        self.status = "ok"
        self.last_error = ""
        self.logger.info("led_command | command=%s", command)
        return True

    def _fail(self, message: str) -> bool:
        self.status = "error"
        self.last_error = message
        self.logger.error("led_error | %s", message)
        return False
