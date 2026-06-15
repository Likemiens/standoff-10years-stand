from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any


def get_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT_DIR = get_root_dir()

DEFAULT_CONFIG: dict[str, Any] = {
    "serial": {
        "enabled": True,
        "mode": "dual_digit",
        "port": "auto",
        "baudRate": 9600,
        "lineEnding": "\n",
        "reconnectIntervalMs": 2000,
        "dual": {
            "tensPort": "auto",
            "onesPort": "auto",
            "ledTarget": "tens",
        },
    },
    "input": {
        "yearPrefix": "20",
        "expectedFormat": "YY",
        "stabilizationDelayMs": 700,
        "duplicateBlockMs": 1000,
        "triggerOnStartup": False,
    },
    "content": {
        "path": "./content",
        "validYearsFrom": 2016,
        "validYearsTo": 2026,
        "yearFilePattern": "standoff_{year}.mp4",
        "idle": "standoff_idle.mp4",
        "beforeRange": "standoff_before_2016.mp4",
        "afterRange": "standoff_after_2026.mp4",
        "returnToIdleAfterVideo": True,
        "returnToIdleDelayMs": 1500,
        "staticDisplayMs": 8000,
    },
    "display": {
        "fullscreen": True,
        "screenIndex": 0,
        "backgroundColor": "#000000",
        "hideCursor": True,
        "keepAspectRatio": True,
    },
    "led": {
        "enabled": False,
        "mode": "serial",
        "port": "shared",
        "baudRate": 9600,
        "lineEnding": "\n",
        "openDelayMs": 1500,
        "chip": "unknown",
        "voltage": 12,
        "powerPerMeterW": 18,
        "runCommand": "LED_RUN",
        "outOfRangeCommand": "LED_ERROR",
        "offCommand": "LED_OFF",
        "idleCommand": "LED_IDLE",
        "errorCommand": "LED_ERROR",
        "runDelayMs": 1200,
        "outOfRangeDurationMs": 7000,
    },
    "debug": {"enabled": True, "showOnStart": False, "hotkey": "F1"},
    "manual": {"enabled": True, "hotkey": "F2"},
    "logging": {"enabled": True, "path": "./logs/events.log"},
}


def merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result


def project_path(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def load_config(config_path: str | Path = "config.json") -> dict[str, Any]:
    path = project_path(config_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
    else:
        loaded = {}

    config = merge_config(DEFAULT_CONFIG, loaded)
    config["_paths"] = {"root": str(ROOT_DIR), "config": str(path)}

    project_path(config["content"]["path"]).mkdir(parents=True, exist_ok=True)
    log_path = project_path(config["logging"]["path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)

    return config
