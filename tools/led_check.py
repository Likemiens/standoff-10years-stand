from __future__ import annotations

import argparse
import time


LINE_ENDINGS = {
    "lf": "\n",
    "crlf": "\r\n",
    "cr": "\r",
    "none": "",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send LED test commands to a serial port")
    parser.add_argument("--port", required=True, help="LED COM port, for example COM5")
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate")
    parser.add_argument("--line-ending", choices=tuple(LINE_ENDINGS), default="lf", help="Command line ending")
    parser.add_argument("--open-delay-ms", type=int, default=2000, help="Delay after opening port")
    parser.add_argument("--interval-ms", type=int, default=1500, help="Delay between commands")
    parser.add_argument(
        "--command",
        action="append",
        dest="commands",
        help="Command to send. Can be passed multiple times.",
    )
    parser.add_argument("--read-after-ms", type=int, default=300, help="Read possible Arduino response after each command")
    return parser.parse_args()


def list_ports() -> None:
    from serial.tools import list_ports

    print("COM ports:")
    ports = list(list_ports.comports())
    if not ports:
        print("  - none")
        return
    for port in ports:
        print(f"  - {port.device}: {port.description}")


def read_available(serial_port: object, duration_ms: int) -> None:
    if duration_ms <= 0:
        return
    deadline = time.time() + duration_ms / 1000
    while time.time() < deadline:
        raw = serial_port.readline()
        if raw:
            text = raw.decode("utf-8", errors="replace").strip()
            print(f"  received: {text!r}")


def main() -> int:
    args = parse_args()
    commands = args.commands or ["LED_IDLE", "LED_RUN", "LED_OFF", "LED_ERROR"]
    ending = LINE_ENDINGS[args.line_ending]

    try:
        import serial
    except ImportError:
        print("ERROR: pyserial is not installed")
        return 1

    list_ports()
    print("")
    print(f"Opening {args.port} at {args.baud} baud")

    try:
        with serial.Serial(args.port, args.baud, timeout=0.2, write_timeout=1) as serial_port:
            if args.open_delay_ms > 0:
                print(f"Waiting {args.open_delay_ms}ms after open")
                time.sleep(args.open_delay_ms / 1000)

            for command in commands:
                payload = f"{command}{ending}".encode("utf-8")
                print(f"sending: {command!r}")
                serial_port.write(payload)
                serial_port.flush()
                read_available(serial_port, args.read_after_ms)
                time.sleep(args.interval_ms / 1000)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1

    print("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
