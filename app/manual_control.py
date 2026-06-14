from __future__ import annotations

from PySide6.QtCore import Qt, QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.constants import SCENARIO_AFTER, SCENARIO_BEFORE, SCENARIO_IDLE


class ManualControl(QWidget):
    yySubmitted = Signal(str)
    yearRequested = Signal(int)
    scenarioRequested = Signal(str)
    ledRequested = Signal(str)

    def __init__(self, year_from: int = 2016, year_to: int = 2026):
        super().__init__()
        self.setWindowTitle("Standoff Manual")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(460)
        self.setStyleSheet(
            "QWidget { background: #151515; color: #f5f5f5; font-size: 14px; }"
            "QPushButton { padding: 8px 10px; background: #262626; border: 1px solid #404040; border-radius: 4px; }"
            "QPushButton:hover { background: #333333; }"
            "QLineEdit { padding: 8px; background: #0a0a0a; border: 1px solid #525252; border-radius: 4px; color: #ffffff; }"
            "QGroupBox { border: 1px solid #333333; margin-top: 12px; padding: 12px 8px 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #d4d4d4; }"
        )

        root = QVBoxLayout(self)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("YY"))
        self.yy_input = QLineEdit()
        self.yy_input.setMaxLength(2)
        self.yy_input.setPlaceholderText("00-99")
        self.yy_input.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,2}"), self))
        self.yy_input.returnPressed.connect(self._submit_yy)
        input_row.addWidget(self.yy_input, 1)
        submit_button = QPushButton("Запустить")
        submit_button.clicked.connect(self._submit_yy)
        input_row.addWidget(submit_button)
        root.addLayout(input_row)

        years_group = QGroupBox("Ролики 2016-2026")
        years_grid = QGridLayout(years_group)
        for index, year in enumerate(range(year_from, year_to + 1)):
            button = QPushButton(str(year))
            button.clicked.connect(lambda checked=False, selected=year: self.yearRequested.emit(selected))
            years_grid.addWidget(button, index // 4, index % 4)
        root.addWidget(years_group)

        scenarios_group = QGroupBox("Сценарии")
        scenarios_row = QHBoxLayout(scenarios_group)
        for title, scenario in (
            ("Idle", SCENARIO_IDLE),
            ("Before 2016", SCENARIO_BEFORE),
            ("After 2026", SCENARIO_AFTER),
        ):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, selected=scenario: self.scenarioRequested.emit(selected))
            scenarios_row.addWidget(button)
        root.addWidget(scenarios_group)

        led_group = QGroupBox("LED")
        led_row = QHBoxLayout(led_group)
        for title, command in (
            ("RUN", "run"),
            ("OFF", "off"),
            ("IDLE", "idle"),
            ("ERROR", "error"),
        ):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, selected=command: self.ledRequested.emit(selected))
            led_row.addWidget(button)
        root.addWidget(led_group)

    def _submit_yy(self) -> None:
        value = self.yy_input.text().strip()
        if len(value) != 2:
            self.yy_input.setFocus()
            return
        self.yySubmitted.emit(value)
