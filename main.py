from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtWidgets import QApplication

from app.config import load_config
from app.constants import SCENARIO_AFTER, SCENARIO_BEFORE, SCENARIO_IDLE
from app.content_resolver import ContentResolver
from app.dual_serial_client import DualDigitSerialClient
from app.led_controller import LedController
from app.logger import setup_logger
from app.manual_control import ManualControl
from app.serial_command_sender import SerialCommandSender
from app.serial_client import SerialClient
from app.state_machine import StandoffStateMachine
from app.ui_debug import DebugPanel
from app.ui_main import MainWindow


class GlobalHotkeyFilter(QObject):
    def __init__(self, window: MainWindow):
        super().__init__()
        self.window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_F1:
                self.window.debugToggleRequested.emit()
                return True
            if key == Qt.Key_F2:
                self.window.manualToggleRequested.emit()
                return True
            if self.window.simulate and key == Qt.Key_I:
                self.window.simulateActionRequested.emit("idle")
                return True
            if self.window.simulate and key == Qt.Key_B:
                self.window.simulateActionRequested.emit("before_2016")
                return True
            if self.window.simulate and key == Qt.Key_A:
                self.window.simulateActionRequested.emit("after_2026")
                return True
            if self.window.simulate and key == Qt.Key_V:
                self.window.simulateActionRequested.emit("2017")
                return True
        return super().eventFilter(watched, event)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standoff History local app")
    parser.add_argument("--config", default="config.json", help="Path to config JSON")
    parser.add_argument("--simulate", action="store_true", help="Run without Arduino and enable keyboard shortcuts")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    logger = setup_logger(config)
    logger.info("app_start | simulate=%s | config=%s", str(args.simulate).lower(), config["_paths"]["config"])

    qt_app = QApplication([sys.argv[0]])

    resolver = ContentResolver(config)
    content_check = resolver.check_content()

    serial_client: SerialClient | DualDigitSerialClient | None = None
    if config["serial"].get("enabled", True) and not args.simulate:
        serial_mode = str(config["serial"].get("mode", "single_yy")).lower()
        if serial_mode == "dual_digit":
            serial_client = DualDigitSerialClient(config["serial"], logger)
        else:
            serial_client = SerialClient(config["serial"], logger, name="arduino_single")
    elif args.simulate:
        logger.info("simulate_mode_enabled")

    led_serial_sender: SerialCommandSender | None = None
    led_sender = serial_client
    led_port = str(config["led"].get("port", "shared")).strip()
    if (
        config["led"].get("enabled", False)
        and str(config["led"].get("mode", "serial")).lower() == "serial"
        and led_port.lower() not in {"", "shared"}
        and not args.simulate
    ):
        led_serial_sender = SerialCommandSender(config["led"], logger, name="led")
        led_sender = led_serial_sender

    led = LedController(config["led"], logger, led_sender)
    state = StandoffStateMachine(config, resolver, led, logger, content_check)

    window = MainWindow(config, simulate=args.simulate)
    debug_panel = DebugPanel()
    manual_panel = ManualControl(resolver.valid_years_from, resolver.valid_years_to)
    hotkey_filter = GlobalHotkeyFilter(window)
    qt_app.installEventFilter(hotkey_filter)

    state.contentRequested.connect(window.show_content)
    state.debugChanged.connect(debug_panel.update_state)
    window.contentFinished.connect(state.handle_content_finished)
    window.playbackError.connect(state.handle_playback_error)

    window.debugToggleRequested.connect(lambda: debug_panel.setVisible(not debug_panel.isVisible()))
    window.manualToggleRequested.connect(lambda: manual_panel.setVisible(not manual_panel.isVisible()))

    manual_panel.yySubmitted.connect(lambda yy: state.submit_value(yy, source="manual", force=True))
    manual_panel.yearRequested.connect(lambda year: state.play_year(year, source="manual"))
    manual_panel.scenarioRequested.connect(lambda scenario: state.play_named_scenario(scenario, source="manual"))
    manual_panel.ledRequested.connect(state.send_led_command)

    def handle_simulate_action(action: str) -> None:
        if action == "idle":
            state.play_named_scenario(SCENARIO_IDLE, source="simulate")
        elif action == "before_2016":
            state.play_named_scenario(SCENARIO_BEFORE, source="simulate")
        elif action == "after_2026":
            state.play_named_scenario(SCENARIO_AFTER, source="simulate")
        elif action == "2017":
            state.play_year(2017, source="simulate")

    window.simulateActionRequested.connect(handle_simulate_action)

    if serial_client is not None:
        serial_client.rawLineReceived.connect(state.handle_serial_raw)
        serial_client.validValueReceived.connect(lambda value: state.submit_value(value, source="arduino", force=False))
        serial_client.invalidLineReceived.connect(lambda raw: state.handle_invalid_input(raw, source="arduino"))
        serial_client.statusChanged.connect(state.set_serial_status)
        serial_client.errorOccurred.connect(state.handle_serial_error)
        qt_app.aboutToQuit.connect(serial_client.stop)
    if led_serial_sender is not None:
        qt_app.aboutToQuit.connect(led_serial_sender.stop)

    window.show_configured()
    if bool(config["debug"].get("showOnStart", False)):
        debug_panel.show()

    if led_serial_sender is not None:
        led_serial_sender.start()

    state.start()
    if serial_client is not None:
        serial_client.start()

    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
