from __future__ import annotations

VALID_YY_PATTERN = r"^\d{2}$"

SCENARIO_IDLE = "idle"
SCENARIO_VIDEO = "video"
SCENARIO_BEFORE = "before_2016"
SCENARIO_AFTER = "after_2026"

CONTENT_KIND_VIDEO = "video"
CONTENT_KIND_IMAGE = "image"
CONTENT_KIND_MISSING = "missing"

VIDEO_EXTENSIONS = (".mp4",)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
CONTENT_EXTENSIONS = VIDEO_EXTENSIONS + IMAGE_EXTENSIONS

SERIAL_PORT_KEYWORDS = ("arduino", "ch340", "usb serial", "nano")
