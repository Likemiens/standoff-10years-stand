from __future__ import annotations

import argparse
import re
import sys
import threading
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.constants import SERIAL_PORT_KEYWORDS, VALID_YY_PATTERN
from app.dual_digit_parser import parse_dual_digit_value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Arduino serial input")
    parser.add_argument("--mode", choices=("single_yy", "dual_digit"), default="dual_digit", help="Input mode")
    parser.add_argument("--port", default="auto", help="COM port or auto")
    parser.add_argument("--tens-port", default="auto", help="COM port for tens Arduino in dual_digit mode")
    parser.add_argument("--ones-port", default="auto", help="COM port for ones Arduino in dual_digit mode")
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


def choose_dual_ports(tens_port: str, ones_port: str, ports: list[object]) -> tuple[str | None, str | None]:
    ordered = [getattr(port, "device", "") for port in ports]

    selected_tens = None if tens_port.lower() == "auto" else tens_port
    selected_ones = None if ones_port.lower() == "auto" else ones_port

    def pick(exclude: set[str]) -> str | None:
        for device in ordered:
            if device and device not in exclude:
                return device
        return None

    if selected_tens is None:
        selected_tens = pick({selected_ones} if selected_ones else set())
    if selected_ones is None:
        selected_ones = pick({selected_tens} if selected_tens else set())

    if selected_tens == selected_ones:
        selected_ones = None
    return selected_tens, selected_ones


def read_single(serial_module: object, port: str, baud: int, seconds: int) -> int:
    print(f"\nOpening {port} at {baud} baud for {seconds}s")
    deadline = time.time() + seconds
    try:
        with serial_module.Serial(port, baud, timeout=0.5) as serial_port:
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


def read_dual(serial_module: object, tens_port: str, ones_port: str, baud: int, seconds: int) -> int:
    print(f"\nOpening tens={tens_port}, ones={ones_port} at {baud} baud for {seconds}s")
    deadline = time.time() + seconds
    lock = threading.Lock()
    digits = {"tens": "", "ones": ""}
    errors: list[str] = []

    def reader(role: str, port: str) -> None:
        try:
            with serial_module.Serial(port, baud, timeout=0.5) as serial_port:
                while time.time() < deadline:
                    raw = serial_port.readline()
                    if not raw:
                        continue
                    text = raw.decode("utf-8", errors="replace").strip()
                    parsed = parse_dual_digit_value(text, fallback_role=role)
                    with lock:
                        print(f"{role} {'valid' if parsed else 'invalid'}: {text!r}")
                        if parsed:
                            effective_role, digit = parsed
                            if effective_role != role or text != digit:
                                print(f"  parsed as {effective_role}={digit}")
                            digits[effective_role] = digit
                            if digits["tens"] and digits["ones"]:
                                print(f"combined YY: {digits['tens']}{digits['ones']}")
        except Exception as exc:
            with lock:
                message = f"{role} ERROR: {type(exc).__name__}: {exc}"
                errors.append(message)
                print(message)

    threads = [
        threading.Thread(target=reader, args=("tens", tens_port), daemon=True),
        threading.Thread(target=reader, args=("ones", ones_port), daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(max(0.1, seconds + 1))

    return 1 if errors else 0


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

    if args.mode == "single_yy":
        selected_port = choose_port(args.port, ports)
        if not selected_port:
            print("ERROR: COM port not found")
            return 1
        return read_single(serial, selected_port, args.baud, args.seconds)

    tens_port, ones_port = choose_dual_ports(args.tens_port, args.ones_port, ports)
    if not tens_port or not ones_port:
        print(f"ERROR: dual COM ports not found. tens={tens_port or '-'} ones={ones_port or '-'}")
        return 1

    return read_dual(serial, tens_port, ones_port, args.baud, args.seconds)


if __name__ == "__main__":
    raise SystemExit(main())
