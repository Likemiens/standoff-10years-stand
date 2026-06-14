from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QStackedWidget

from app.constants import CONTENT_KIND_IMAGE, CONTENT_KIND_VIDEO, SCENARIO_IDLE


class MainWindow(QMainWindow):
    contentFinished = Signal()
    playbackError = Signal(str)
    debugToggleRequested = Signal()
    manualToggleRequested = Signal()
    simulateActionRequested = Signal(str)

    def __init__(self, config: dict[str, Any], simulate: bool = False):
        super().__init__()
        self.config = config
        self.simulate = simulate
        self.display_config = config["display"]
        self.content_config = config["content"]
        self.current_loop = False
        self.current_content = None
        self._source_pixmap: QPixmap | None = None

        self.setWindowTitle("Standoff History")
        self.setStyleSheet(f"background: {self.display_config.get('backgroundColor', '#000000')};")

        self.stack = QStackedWidget(self)
        self.setCentralWidget(self.stack)

        self.video_widget = QVideoWidget(self)
        self.video_widget.setStyleSheet("background: #000000;")
        self.stack.addWidget(self.video_widget)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background: #000000;")
        self.stack.addWidget(self.image_label)

        self.message_label = QLabel(self)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(
            "background: #000000; color: #ffffff; font-size: 28px; padding: 48px;"
        )
        self.stack.addWidget(self.message_label)

        self.audio_output = QAudioOutput(self)
        self.audio_output.setMuted(True)
        self.audio_output.setVolume(0)

        self.player = QMediaPlayer(self)
        self.player.setVideoOutput(self.video_widget)
        self.player.setAudioOutput(self.audio_output)
        self.player.mediaStatusChanged.connect(self._handle_media_status)
        self.player.errorOccurred.connect(self._handle_player_error)

        self.static_timer = QTimer(self)
        self.static_timer.setSingleShot(True)
        self.static_timer.timeout.connect(self.contentFinished.emit)

        if bool(self.display_config.get("hideCursor", True)):
            self.setCursor(QCursor(Qt.BlankCursor))

    def show_configured(self) -> None:
        app = QApplication.instance()
        screens = app.screens() if app else []
        screen_index = int(self.display_config.get("screenIndex", 0))
        if screens:
            screen = screens[min(max(screen_index, 0), len(screens) - 1)]
            self.setGeometry(screen.geometry())

        if bool(self.display_config.get("fullscreen", True)):
            self.showFullScreen()
        else:
            self.resize(1280, 720)
            self.show()

    def show_content(self, content: Any, loop: bool = False) -> None:
        self.static_timer.stop()
        self.player.stop()
        self.current_content = content
        self.current_loop = loop
        self._source_pixmap = None

        if not getattr(content, "exists", False):
            self._show_message(
                "Контент не найден\n"
                f"{getattr(content, 'expected_name', '-')}\n\n"
                "F1 - debug, F2 - ручной режим"
            )
            if getattr(content, "scenario", "") != SCENARIO_IDLE:
                self.static_timer.start(int(self.content_config.get("staticDisplayMs", 8000)))
            return

        path = Path(content.path)
        kind = getattr(content, "kind", "")
        if kind == CONTENT_KIND_VIDEO:
            self.stack.setCurrentWidget(self.video_widget)
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.player.play()
            return

        if kind == CONTENT_KIND_IMAGE:
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                self.playbackError.emit(f"Cannot load image: {path.name}")
                self._show_message(f"Не удалось загрузить изображение\n{path.name}")
                return
            self._source_pixmap = pixmap
            self.stack.setCurrentWidget(self.image_label)
            self._rescale_image()
            if not loop:
                self.static_timer.start(int(self.content_config.get("staticDisplayMs", 8000)))
            return

        self._show_message(f"Неподдерживаемый тип контента\n{path.name}")
        self.playbackError.emit(f"Unsupported content type: {path.name}")

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if self._source_pixmap is not None:
            self._rescale_image()

    def keyPressEvent(self, event: Any) -> None:
        key = event.key()
        if key == Qt.Key_F1:
            self.debugToggleRequested.emit()
            return
        if key == Qt.Key_F2:
            self.manualToggleRequested.emit()
            return
        if self.simulate:
            if key == Qt.Key_I:
                self.simulateActionRequested.emit("idle")
                return
            if key == Qt.Key_B:
                self.simulateActionRequested.emit("before_2016")
                return
            if key == Qt.Key_A:
                self.simulateActionRequested.emit("after_2026")
                return
            if key == Qt.Key_V:
                self.simulateActionRequested.emit("2017")
                return
        super().keyPressEvent(event)

    def _rescale_image(self) -> None:
        if self._source_pixmap is None:
            return
        size = self.image_label.size()
        scaled = self._source_pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)

    def _show_message(self, text: str) -> None:
        self.message_label.setText(text)
        self.stack.setCurrentWidget(self.message_label)

    def _handle_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status != QMediaPlayer.EndOfMedia:
            return
        if self.current_loop:
            self.player.setPosition(0)
            self.player.play()
            return
        self.contentFinished.emit()

    def _handle_player_error(self, error: QMediaPlayer.Error, error_string: str = "") -> None:
        if error == QMediaPlayer.NoError:
            return
        message = error_string or str(error)
        self._show_message(f"Ошибка воспроизведения\n{message}")
        self.playbackError.emit(message)
