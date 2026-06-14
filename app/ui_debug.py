from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget


class DebugPanel(QWidget):
    FIELDS = (
        ("arduino_status", "Arduino status"),
        ("com_port", "COM-port"),
        ("last_raw_input", "Last raw input"),
        ("candidate_value", "Candidate value"),
        ("stable_value", "Stable value"),
        ("last_triggered_value", "Last triggered value"),
        ("mapped_year", "Mapped year"),
        ("current_scenario", "Current scenario"),
        ("current_file", "Current file"),
        ("led_status", "LED status"),
        ("last_led_command", "Last LED command"),
        ("last_error", "Last error"),
        ("content_check_status", "Content check status"),
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Standoff Debug")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(520)
        self.setStyleSheet(
            "QWidget { background: #111111; color: #f5f5f5; font-size: 14px; }"
            "QLabel { padding: 4px; }"
        )

        layout = QGridLayout(self)
        layout.setColumnStretch(1, 1)
        self.value_labels: dict[str, QLabel] = {}

        for row, (key, title) in enumerate(self.FIELDS):
            title_label = QLabel(title)
            title_label.setStyleSheet("color: #a3a3a3;")
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setWordWrap(True)
            layout.addWidget(title_label, row, 0)
            layout.addWidget(value_label, row, 1)
            self.value_labels[key] = value_label

    def update_state(self, state: dict[str, Any]) -> None:
        for key, label in self.value_labels.items():
            label.setText(str(state.get(key, "-")))
