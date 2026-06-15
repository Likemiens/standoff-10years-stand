from __future__ import annotations

import logging
import re
import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from app.constants import SCENARIO_AFTER, SCENARIO_BEFORE, SCENARIO_IDLE, SCENARIO_VIDEO, VALID_YY_PATTERN
from app.content_resolver import ContentCheckResult, ContentResolver, ResolvedContent
from app.led_controller import LedController


class StandoffStateMachine(QObject):
    contentRequested = Signal(object, bool)
    debugChanged = Signal(dict)

    def __init__(
        self,
        config: dict[str, Any],
        resolver: ContentResolver,
        led_controller: LedController,
        logger: logging.Logger,
        content_check: ContentCheckResult,
    ):
        super().__init__()
        self.config = config
        self.resolver = resolver
        self.led = led_controller
        self.logger = logger
        self.content_check = content_check

        self.serial_connected = False
        self.com_port = ""
        self.last_raw_input = ""
        self.candidate_value = ""
        self.candidate_source = ""
        self.stable_value = ""
        self.last_triggered_value = ""
        self.last_triggered_at_ms = 0.0
        self.startup_stable_seen = False
        self.startup_stable_value = ""
        self.mapped_year = ""
        self.current_scenario = SCENARIO_IDLE
        self.current_file = ""
        self.last_error = ""
        self._pending_content: ResolvedContent | None = None

        self._stabilization_timer = QTimer(self)
        self._stabilization_timer.setSingleShot(True)
        self._stabilization_timer.timeout.connect(self._accept_candidate)

        self._led_delay_timer = QTimer(self)
        self._led_delay_timer.setSingleShot(True)
        self._led_delay_timer.timeout.connect(self._start_pending_content)

        self._led_off_timer = QTimer(self)
        self._led_off_timer.setSingleShot(True)
        self._led_off_timer.timeout.connect(self._turn_led_off)

        self._return_idle_timer = QTimer(self)
        self._return_idle_timer.setSingleShot(True)
        self._return_idle_timer.timeout.connect(lambda: self.show_idle("return_to_idle"))

    def start(self) -> None:
        self.logger.info("app_ready | content_check=%s", self.content_check.summary)
        if not self.content_check.ok:
            self.last_error = f"Content check: {self.content_check.summary}"
            self.logger.error("content_check_error | %s", self.last_error)
        self.show_idle("startup")
        self._emit_debug()

    def set_serial_status(self, connected: bool, port: str) -> None:
        self.serial_connected = connected
        self.com_port = port or self.com_port
        self._emit_debug()

    def handle_serial_raw(self, raw: str) -> None:
        self.last_raw_input = raw
        self._emit_debug()

    def handle_invalid_input(self, raw: str, source: str = "arduino") -> None:
        self.last_raw_input = raw
        self.last_error = f"Invalid input from {source}: {raw!r}"
        self.logger.warning("invalid_input | source=%s | raw=%r", source, raw)
        self._emit_debug()

    def handle_serial_error(self, message: str) -> None:
        self.last_error = message
        self.logger.error("serial_error | %s", message)
        self._emit_debug()

    def submit_value(self, value: str, source: str = "arduino", force: bool = False) -> None:
        clean_value = value.strip()
        self.last_raw_input = clean_value

        if not re.fullmatch(VALID_YY_PATTERN, clean_value):
            self.handle_invalid_input(clean_value, source)
            return

        self.logger.info("valid_input | source=%s | raw=%s", source, clean_value)

        if force:
            self.candidate_value = clean_value
            self.stable_value = clean_value
            self._trigger_value(clean_value, source, force=True)
            return

        self.candidate_value = clean_value
        self.candidate_source = source
        delay_ms = int(self.config["input"].get("stabilizationDelayMs", 700))
        self._stabilization_timer.start(delay_ms)
        self._emit_debug()

    def play_year(self, year: int, source: str = "manual") -> None:
        if year < self.resolver.valid_years_from or year > self.resolver.valid_years_to:
            self.last_error = f"Manual year is out of valid video range: {year}"
            self._emit_debug()
            return
        self.submit_value(f"{year % 100:02d}", source=source, force=True)

    def play_named_scenario(self, scenario: str, source: str = "manual") -> None:
        if scenario == SCENARIO_IDLE:
            self.show_idle(source)
            return
        if scenario not in {SCENARIO_BEFORE, SCENARIO_AFTER}:
            self.last_error = f"Unknown manual scenario: {scenario}"
            self._emit_debug()
            return

        resolved = self.resolver.resolve_named(scenario)
        self.logger.info("manual_launch | scenario=%s | file=%s", scenario, resolved.file_name)
        self._return_idle_timer.stop()
        self._led_delay_timer.stop()
        self._led_off_timer.stop()
        self._pending_content = None
        self._send_pre_content_led(resolved)
        self._play_content(resolved)

    def send_led_command(self, command_name: str) -> None:
        command_map = {
            "run": self.led.send_run,
            "off": self.led.send_off,
            "idle": self.led.send_idle,
            "error": self.led.send_error,
        }
        sender = command_map.get(command_name)
        if sender is None:
            self.last_error = f"Unknown LED command: {command_name}"
            self._emit_debug()
            return
        sender()
        if self.led.last_error:
            self.last_error = self.led.last_error
        self._emit_debug()

    def handle_content_finished(self) -> None:
        if self.current_scenario == SCENARIO_IDLE:
            return
        if self.current_scenario == SCENARIO_VIDEO:
            self._turn_led_off()
        if not bool(self.config["content"].get("returnToIdleAfterVideo", True)):
            return
        delay_ms = int(self.config["content"].get("returnToIdleDelayMs", 1500))
        self._return_idle_timer.start(delay_ms)

    def handle_playback_error(self, message: str) -> None:
        self.last_error = message
        self.logger.error("playback_error | %s", message)
        self._emit_debug()
        if self.current_scenario != SCENARIO_IDLE:
            self._return_idle_timer.start(500)

    def show_idle(self, source: str = "system") -> None:
        self._led_delay_timer.stop()
        self._led_off_timer.stop()
        self._return_idle_timer.stop()
        self._pending_content = None
        resolved = self.resolver.resolve_named(SCENARIO_IDLE)
        self.current_scenario = SCENARIO_IDLE
        self.current_file = resolved.file_name
        self.mapped_year = ""
        self.led.send_off()
        if resolved.error:
            self.last_error = resolved.error
            self.logger.error("content_error | scenario=idle | error=%s", resolved.error)
        self.logger.info("show_idle | source=%s | file=%s", source, resolved.file_name)
        self.contentRequested.emit(resolved, True)
        self._emit_debug()

    def _accept_candidate(self) -> None:
        value = self.candidate_value
        source = self.candidate_source or "arduino"
        if not value:
            return

        self.stable_value = value
        self.logger.info("stable_value | source=%s | stable=%s", source, value)

        trigger_on_startup = bool(self.config["input"].get("triggerOnStartup", False))
        if source == "arduino" and not self.startup_stable_seen and not trigger_on_startup:
            self.startup_stable_seen = True
            self.startup_stable_value = value
            self.logger.info("startup_value_suppressed | stable=%s", value)
            self._emit_debug()
            return

        self.startup_stable_seen = True
        if (
            source == "arduino"
            and self.startup_stable_value == value
            and not self.last_triggered_value
        ):
            self.logger.info("duplicate_ignored | source=%s | stable=%s | reason=startup_value", source, value)
            self._emit_debug()
            return

        self._trigger_value(value, source, force=False)

    def _trigger_value(self, value: str, source: str, force: bool) -> None:
        now_ms = time.monotonic() * 1000
        duplicate_block_ms = int(self.config["input"].get("duplicateBlockMs", 1000))
        is_duplicate = self.last_triggered_value == value
        recently_triggered = now_ms - self.last_triggered_at_ms < duplicate_block_ms

        if is_duplicate and not force:
            self.logger.info(
                "duplicate_ignored | source=%s | stable=%s | recent=%s",
                source,
                value,
                str(recently_triggered).lower(),
            )
            self._emit_debug()
            return

        self._return_idle_timer.stop()
        self._led_delay_timer.stop()
        self._led_off_timer.stop()
        self._pending_content = None
        self.last_triggered_value = value
        self.last_triggered_at_ms = now_ms

        resolved = self.resolver.resolve_yy(value)
        self.mapped_year = str(resolved.year or "")
        self.current_scenario = resolved.scenario
        self.current_file = resolved.file_name

        if resolved.error:
            self.last_error = resolved.error
            self.logger.error(
                "content_error | source=%s | stable=%s | year=%s | scenario=%s | error=%s",
                source,
                value,
                resolved.year,
                resolved.scenario,
                resolved.error,
            )
        else:
            self.last_error = ""

        self.logger.info(
            "trigger | source=%s | raw=%s | stable=%s | year=%s | scenario=%s | file=%s",
            source,
            value,
            value,
            resolved.year,
            resolved.scenario,
            resolved.file_name,
        )

        led_run_sent = self._send_pre_content_led(resolved)

        if led_run_sent:
            self._pending_content = resolved
            self._led_delay_timer.start(int(self.config["led"].get("runDelayMs", 1200)))
        else:
            self._play_content(resolved)

        self._emit_debug()

    def _start_pending_content(self) -> None:
        if self._pending_content is None:
            return
        content = self._pending_content
        self._pending_content = None
        self._play_content(content)

    def _turn_led_off(self) -> None:
        self.led.send_off()
        if self.led.last_error:
            self.last_error = self.led.last_error
        self._emit_debug()

    def _play_content(self, resolved: ResolvedContent) -> None:
        self.current_scenario = resolved.scenario
        self.current_file = resolved.file_name
        if resolved.year is not None:
            self.mapped_year = str(resolved.year)
        else:
            self.mapped_year = ""
        if resolved.error:
            self.last_error = resolved.error

        self.contentRequested.emit(resolved, resolved.scenario == SCENARIO_IDLE)
        self.logger.info("play_content | scenario=%s | file=%s | exists=%s", resolved.scenario, resolved.file_name, resolved.exists)

        if self.led.last_error:
            self.last_error = self.led.last_error
        self._emit_debug()

    def _send_pre_content_led(self, resolved: ResolvedContent) -> bool:
        if not self.led.enabled:
            return False
        if resolved.scenario == SCENARIO_VIDEO:
            return self.led.send_run()
        if resolved.scenario in {SCENARIO_BEFORE, SCENARIO_AFTER}:
            sent = self.led.send_out_of_range()
            if sent:
                delay_ms = int(
                    self.config["led"].get(
                        "outOfRangeDurationMs",
                        self.config["led"].get("runDelayMs", 1200),
                    )
                )
                self._led_off_timer.start(delay_ms)
            return False
        return False

    def _emit_debug(self) -> None:
        self.debugChanged.emit(
            {
                "arduino_status": "connected" if self.serial_connected else "disconnected",
                "com_port": self.com_port or "-",
                "last_raw_input": self.last_raw_input or "-",
                "candidate_value": self.candidate_value or "-",
                "stable_value": self.stable_value or "-",
                "last_triggered_value": self.last_triggered_value or "-",
                "mapped_year": self.mapped_year or "-",
                "current_scenario": self.current_scenario or "-",
                "current_file": self.current_file or "-",
                "led_status": self.led.status,
                "last_led_command": self.led.last_command or "-",
                "last_error": self.last_error or "-",
                "content_check_status": self.content_check.summary,
            }
        )
