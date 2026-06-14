from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.constants import SERIAL_PORT_KEYWORDS, VALID_YY_PATTERN


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Arduino serial input")
    parser.add_argument("--port", default="auto", help="COM port or auto")
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate")
    parser.add_argument("--seconds", type=int, default=30, help="Read duration")
    return parser.parse_args()


def list_ports() -> list[object]:
    from serial.tools import list_ports as serial_list_ports

    return list(serial_list_ports.comports())


def choose_port(configured_port: str, ports: list[object]) -> str | None:
    if configured_port.lower() != "auto":
        return configured_port
    if not ports:
        return None

    def searchable(port: object) -> str:
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
    return getattr((preferred or ports)[0], "device", None)


def main() -> int:
    args = parse_args()
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial is not installed")
        return 1

    ports = list_ports()
    print("COM ports:")
    if not ports:
        print("  - none")
    for port in ports:
        print(f"  - {port.device}: {port.description}")

    selected_port = choose_port(args.port, ports)
    if not selected_port:
        print("ERROR: COM port not found")
        return 1

    print(f"\nOpening {selected_port} at {args.baud} baud for {args.seconds}s")
    deadline = time.time() + args.seconds
    try:
        with serial.Serial(selected_port, args.baud, timeout=0.5) as serial_port:
            while time.time() < deadline:
                raw = serial_port.readline()
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="replace").strip()
                status = "valid" if re.fullmatch(VALID_YY_PATTERN, text) else "invalid"
                print(f"{status}: {text!r}")
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
