"""
Shared building blocks for the laser-control CLI tools (single_mega2560.py,
dual_mega2560.py): serial communication, logging, config-file loading,
protocol-file resolution, and CSV parsing/validation.
"""

import csv
import sys
import time
import threading
import tomllib
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────
# Logger
# ─────────────────────────────────────────────
class CommLogger:
    """Timestamped serial communication logger. TX/RX written in chronological order."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.lock = threading.Lock()
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Communication Log - Started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

    def _write(self, direction: str, content: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"[{ts}] {direction}: {content}"
        print(line)
        with self.lock:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def tx(self, content: str):
        self._write("TX >>>", content)

    def rx(self, content: str):
        self._write("RX <<<", content)

    def note(self, content: str):
        self._write("NOTE  ", content)


# ─────────────────────────────────────────────
# Serial interface
# ─────────────────────────────────────────────
class SerialInterface:
    """Serial port wrapper with automatic logging."""

    def __init__(self, name: str, port: str, baudrate: int, timeout: float, logger: CommLogger):
        import serial  # deferred import so --help works without pyserial installed

        self.name = name
        self.logger = logger
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        time.sleep(0.5)
        self.ser.reset_input_buffer()
        self.logger.note(f"Connected to {port} @ {baudrate} baud")

    def send(self, cmd: str):
        """Send a command (appends \\r\\n automatically)."""
        self.logger.tx(cmd)
        self.ser.write((cmd + "\r\n").encode("ascii"))

    def readline(self) -> str:
        """Read one line. Returns empty string on timeout."""
        raw = self.ser.readline()
        line = raw.decode("ascii", errors="replace").strip()
        if line:
            self.logger.rx(line)
        else:
            self.logger.note("(read timeout, no response)")
        return line

    def send_and_read(self, cmd: str) -> str:
        """Send a command and wait for one line of response."""
        self.send(cmd)
        return self.readline()

    def close(self):
        self.ser.close()
        self.logger.note("Port closed")


# ─────────────────────────────────────────────
# Wait for arduino Ready.
# ─────────────────────────────────────────────
def wait_for_ready(arduino: SerialInterface, logger: CommLogger):
    """Block until 'Ready.' is received. Intermediate messages (ACK, P,...) are logged."""
    logger.note("Waiting for arduino Ready...")
    while True:
        msg = arduino.readline()
        if msg == "Ready.":
            logger.note("Received Ready.")
            return
        elif msg:
            logger.note(f"(intermediate: {msg})")


# ─────────────────────────────────────────────
# Protocol (CSV) file resolution
# ─────────────────────────────────────────────
def resolve_protocol_path(raw: str) -> Path:
    """
    Turn a user-supplied path string into an absolute Path, tolerant of the
    quirks of pasting a Windows "Copy as path" string:
      - strips surrounding whitespace
      - strips a matching pair of leading/trailing quotes, if present
        (harmless no-op if the shell already stripped them)
      - resolves relative paths against the current working directory

    Raises FileNotFoundError (with the resolved absolute path in the message)
    if the file doesn't exist, so a bad paste is easy to diagnose.
    """
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1]
    path = Path(s).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Protocol file not found: {path}")
    return path


def confirm_default_protocol(default_path: Path) -> Path:
    """
    Ask the operator (on stdin) to confirm falling back to the default
    protocol file when none was given on the command line. Only an explicit
    y/yes proceeds; anything else (including a bare Enter) aborts before any
    serial port is touched.
    """
    print("No protocol file specified. The default protocol file will be used:")
    print(f"  {default_path}")
    answer = input("Continue with this file? [y/N]: ").strip().lower()
    if answer not in ("y", "yes"):
        print("Aborted. Pass a protocol file path to use a different one, e.g.:")
        print(f"  {Path(sys.argv[0]).name} path\\to\\your_protocol.csv")
        sys.exit(1)
    return default_path


# ─────────────────────────────────────────────
# Config file (TOML)
# ─────────────────────────────────────────────
def load_config(config_path: Path, defaults: dict) -> dict:
    """
    Load a TOML config file and shallow-merge it onto `defaults` (keys not
    present in the file fall back to the default value). Raises
    FileNotFoundError if config_path doesn't exist.
    """
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    config = dict(defaults)
    config.update(data)
    return config


# ─────────────────────────────────────────────
# Log directory
# ─────────────────────────────────────────────
def new_run_log_dir(base_log_dir: Path) -> Path:
    """Create and return base_log_dir/<timestamp>/ for one run's logs."""
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = base_log_dir / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


# ─────────────────────────────────────────────
# CSV parameter file
# ─────────────────────────────────────────────
class ProtocolValidationError(ValueError):
    """Raised when one or more rows in a protocol CSV fail validation."""


def read_csv_rows(filepath: Path) -> list:
    """
    Read a CSV file and normalize header names (stripped, lowercased, spaces
    -> underscores), so 'pulse width' and 'pulse_width' are both accepted.
    Values are returned as stripped strings; numeric parsing/validation is
    left to the caller (see `positive_int`).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    rows = []
    for row in raw_rows:
        rows.append({k.strip().lower().replace(" ", "_"): (v or "").strip() for k, v in row.items()})
    return rows


def positive_int(raw: str) -> int:
    """Parse `raw` as a positive integer. Raises ValueError if it isn't one."""
    value = int(raw)
    if value <= 0:
        raise ValueError("must be a positive integer")
    return value


def raise_if_errors(errors: list, filepath: Path):
    """Raise ProtocolValidationError listing every collected row error, if any."""
    if errors:
        details = "\n  ".join(errors)
        raise ProtocolValidationError(
            f"Invalid protocol file: {filepath}\n  {details}"
        )
