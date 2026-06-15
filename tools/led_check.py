from __future__ import annotations

import argparse
import time


LINE_ENDINGS = {
    "lf": "\n",
    "crlf": "\r\n",
    "cr": "\r",
    "none": "",
}

PROBE_BAUDS = (9600, 115200)
PROBE_LINE_ENDINGS = ("lf", "crlf")
PROBE_COMMANDS = (
    "LED_IDLE",
    "LED_RUN",
    "LED_OFF",
    "RUN",
    "OFF",
    "ON",
    "0",
    "1",
)


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
    parser.add_argument("--probe", action="store_true", help="Try common baud rates, line endings, and commands")
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


def send_commands(
    serial_module: object,
    port: str,
    baud: int,
    line_ending: str,
    commands: list[str] | tuple[str, ...],
    open_delay_ms: int,
    interval_ms: int,
    read_after_ms: int,
) -> int:
    ending = LINE_ENDINGS[line_ending]
    try:
        with serial_module.Serial(port, baud, timeout=0.2, write_timeout=1) as serial_port:
            if open_delay_ms > 0:
                print(f"Waiting {open_delay_ms}ms after open")
                time.sleep(open_delay_ms / 1000)

            for command in commands:
                payload = f"{command}{ending}".encode("utf-8")
                print(f"sending: {command!r} ending={line_ending}")
                serial_port.write(payload)
                serial_port.flush()
                read_available(serial_port, read_after_ms)
                time.sleep(interval_ms / 1000)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1

    return 0


def main() -> int:
    args = parse_args()
    commands = args.commands or ["LED_IDLE", "LED_RUN", "LED_OFF", "LED_ERROR"]

    try:
        import serial
    except ImportError:
        print("ERROR: pyserial is not installed")
        return 1

    list_ports()
    print("")

    if args.probe:
        print(f"Probe mode for {args.port}")
        for baud in PROBE_BAUDS:
            for line_ending in PROBE_LINE_ENDINGS:
                print("")
                print(f"Opening {args.port} at {baud} baud, ending={line_ending}")
                result = send_commands(
                    serial,
                    args.port,
                    baud,
                    line_ending,
                    PROBE_COMMANDS,
                    args.open_delay_ms,
                    500,
                    args.read_after_ms,
                )
                if result != 0:
                    return result
        print("Probe done")
        return 0

    print(f"Opening {args.port} at {args.baud} baud")
    result = send_commands(
        serial,
        args.port,
        args.baud,
        args.line_ending,
        commands,
        args.open_delay_ms,
        args.interval_ms,
        args.read_after_ms,
    )
    if result != 0:
        return result

    print("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
