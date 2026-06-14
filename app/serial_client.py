from __future__ import annotations

import logging
import re
import threading
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from app.constants import SERIAL_PORT_KEYWORDS, VALID_YY_PATTERN


def list_serial_ports_ordered() -> list[Any]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []

    ports = list(list_ports.comports())
    if not ports:
        return []

    def searchable(port: Any) -> str:
        return " ".join(
            str(value)
            for value in (
                getattr(port, "device", ""),
                getattr(port, "description", ""),
                getattr(port, "manufacturer", ""),
                getattr(port, "hwid", ""),
            )
        ).lower()

    preferred = [port for port in ports if any(keyword in searchable(port) for keyword in SERIAL_PORT_KEYWORDS)]
    other = [port for port in ports if port not in preferred]
    return preferred + other


def find_serial_port(logger: logging.Logger | None = None) -> str | None:
    try:
        ports = list_serial_ports_ordered()
    except Exception as exc:
        if logger:
            logger.error("serial_error | cannot list ports | error=%s", exc)
        return None

    if not ports:
        if logger:
            logger.error("serial_error | no COM ports found")
        return None

    selected = ports[0]

    if logger:
        logger.info(
            "serial_autodetect | selected=%s | candidates=%s",
            selected.device,
            ",".join(port.device for port in ports),
        )
    return selected.device


def find_serial_ports(count: int, logger: logging.Logger | None = None) -> list[str]:
    ports = list_serial_ports_ordered()
    selected = [port.device for port in ports[:count]]
    if logger:
        logger.info(
            "serial_autodetect_many | selected=%s | candidates=%s",
            ",".join(selected) or "-",
            ",".join(port.device for port in ports) or "-",
        )
    return selected


class SerialReaderThread(QThread):
    rawLineReceived = Signal(str)
    validValueReceived = Signal(str)
    invalidLineReceived = Signal(str)
    statusChanged = Signal(bool, str)
    errorOccurred = Signal(str)

    def __init__(
        self,
        port: str,
        baud_rate: int,
        line_ending: str,
        logger: logging.Logger,
        value_pattern: str = VALID_YY_PATTERN,
        name: str = "serial",
    ):
        super().__init__()
        self.port = port
        self.baud_rate = baud_rate
        self.line_ending = line_ending
        self.logger = logger
        self.value_pattern = value_pattern
        self.name = name
        self._stop_event = threading.Event()
        self._write_lock = threading.Lock()
        self._serial = None

    def run(self) -> None:
        try:
            import serial
        except ImportError:
            self.errorOccurred.emit("pyserial is not installed")
            self.statusChanged.emit(False, self.port)
            return

        try:
            with serial.Serial(self.port, self.baud_rate, timeout=0.2, write_timeout=0.5) as serial_port:
                self._serial = serial_port
                self.statusChanged.emit(True, self.port)
                self.logger.info("serial_connected | name=%s | port=%s | baud=%s", self.name, self.port, self.baud_rate)

                while not self._stop_event.is_set():
                    raw_bytes = serial_port.readline()
                    if not raw_bytes:
                        continue

                    raw_text = raw_bytes.decode("utf-8", errors="replace")
                    clean_text = raw_text.strip()
                    self.rawLineReceived.emit(clean_text)

                    if re.fullmatch(self.value_pattern, clean_text):
                        self.validValueReceived.emit(clean_text)
                    else:
                        self.invalidLineReceived.emit(clean_text)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            self.errorOccurred.emit(message)
            self.logger.error("serial_error | name=%s | port=%s | error=%s", self.name, self.port, message)
        finally:
            self._serial = None
            self.statusChanged.emit(False, self.port)
            self.logger.info("serial_disconnected | name=%s | port=%s", self.name, self.port)

    def stop(self) -> None:
        self._stop_event.set()
        with self._write_lock:
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception:
                    pass

    def write_line(self, line: str) -> bool:
        payload = f"{line}{self.line_ending}".encode("utf-8")
        with self._write_lock:
            if self._serial is None or not getattr(self._serial, "is_open", False):
                return False
            try:
                self._serial.write(payload)
                self._serial.flush()
                return True
            except Exception as exc:
                self.errorOccurred.emit(f"Serial write failed: {exc}")
                return False


class SerialClient(QObject):
    rawLineReceived = Signal(str)
    validValueReceived = Signal(str)
    invalidLineReceived = Signal(str)
    statusChanged = Signal(bool, str)
    errorOccurred = Signal(str)

    def __init__(
        self,
        config: dict[str, Any],
        logger: logging.Logger,
        *,
        port: str | None = None,
        value_pattern: str = VALID_YY_PATTERN,
        name: str = "serial",
    ):
        super().__init__()
        self.config = config
        self.logger = logger
        self.enabled = bool(config.get("enabled", True))
        self.configured_port = str(port if port is not None else config.get("port", "auto"))
        self.baud_rate = int(config.get("baudRate", 9600))
        self.line_ending = str(config.get("lineEnding", "\n"))
        self.reconnect_interval_ms = int(config.get("reconnectIntervalMs", 2000))
        self.value_pattern = value_pattern
        self.name = name
        self.connected = False
        self.current_port = ""
        self._worker: SerialReaderThread | None = None
        self._stopping = False

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._connect)

    def start(self) -> None:
        if not self.enabled:
            self.statusChanged.emit(False, "")
            self.logger.info("serial_disabled | name=%s", self.name)
            return
        self._connect()

    def stop(self) -> None:
        self._stopping = True
        self._reconnect_timer.stop()
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(1000)
            self._worker = None

    def write_line(self, line: str) -> bool:
        if not self.connected or self._worker is None:
            return False
        return self._worker.write_line(line)

    def _connect(self) -> None:
        if self._stopping:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        port = self.configured_port
        if port.lower() == "auto":
            port = find_serial_port(self.logger) or ""

        if not port:
            self.connected = False
            self.current_port = ""
            self.errorOccurred.emit(f"Arduino COM port not found: {self.name}")
            self.statusChanged.emit(False, "")
            self.logger.error("serial_error | name=%s | Arduino COM port not found", self.name)
            self._schedule_reconnect()
            return

        self.current_port = port
        self._worker = SerialReaderThread(
            port,
            self.baud_rate,
            self.line_ending,
            self.logger,
            value_pattern=self.value_pattern,
            name=self.name,
        )
        self._worker.rawLineReceived.connect(self.rawLineReceived.emit)
        self._worker.validValueReceived.connect(self.validValueReceived.emit)
        self._worker.invalidLineReceived.connect(self.invalidLineReceived.emit)
        self._worker.errorOccurred.connect(self.errorOccurred.emit)
        self._worker.statusChanged.connect(self._handle_status)
        self._worker.finished.connect(self._handle_finished)
        self._worker.start()

    def _handle_status(self, connected: bool, port: str) -> None:
        self.connected = connected
        self.current_port = port if connected else self.current_port
        self.statusChanged.emit(connected, port)
        if not connected and not self._stopping:
            self._schedule_reconnect()

    def _handle_finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if not self._stopping:
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self.reconnect_interval_ms <= 0 or self._reconnect_timer.isActive():
            return
        self._reconnect_timer.start(self.reconnect_interval_ms)
