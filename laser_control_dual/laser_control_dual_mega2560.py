"""
Laser Controller (Dual Channel)
================================
Controls two laser drivers (blue + red) and a single dual-channel Arduino
board's serial communication sequentially. The Arduino board runs
laser_control_mega2560.ino, which drives BLUE on PIN8 and RED on PIN9, one
pulse train at a time.

COM ports:
    Arduino mega 2560 board (single board, both channels)
        COM port: see CONFIG["arduino_port"]
    Laser drivers (one per color)
        blue laser: CONFIG["blue_laser_port"]
        red  laser: CONFIG["red_laser_port"]

Requirements:
    pip install pyserial

Parameter file : laser_control_protocol_dual_mega2560.csv  (same directory as this script)
                 each row has an extra "color" column (blue/red) selecting
                 which channel and which laser driver that round uses.
Log output     : logs/<timestamp>/blue_laser_communication.txt
                 logs/<timestamp>/red_laser_communication.txt
                 logs/<timestamp>/arduino_communication.txt
"""

import serial
import csv
import time
import threading
from datetime import datetime
from pathlib import Path

# Script directory — all relative paths are resolved from here
SCRIPT_DIR = Path(__file__).parent.resolve()

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
CONFIG = {
    "blue_laser_port":  "COM5",
    "red_laser_port":   "COM6",
    "arduino_port":     "COM3",
    "laser_baudrate":   38400,
    "arduino_baudrate": 115200,
    "timeout":          5.0,    # Serial read timeout (seconds)
    "cmd_interval":     0.1,    # Delay between non-query commands (seconds)
    "latency":          5.0,    # Fixed wait after Ready. before sending params (seconds)
    "final_wait":       1.0,    # Wait after last Ready. before closing lasers (seconds)
    "params_file":      "laser_control_protocol_dual_mega2560.csv",   # Relative to script directory
    "log_dir":          "logs",                         # Relative to script directory
}

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
# Parameter file
# ─────────────────────────────────────────────
def load_params(filepath: Path) -> list:
    """
    Read CSV parameter file.
    Header names are normalized (stripped, lowercased, spaces -> underscores),
    so 'pulse width' and 'pulse_width' are both accepted.
    Each row must include a 'color' column (blue/red, case-insensitive)
    selecting which channel and which laser driver that round uses.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    params = []
    for row in raw_rows:
        normalized = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items()}
        color = normalized.get("color", "").strip().lower()
        if color not in ("blue", "red"):
            raise ValueError(f"Invalid or missing 'color' in CSV row: {row} (expected 'blue' or 'red')")
        params.append({
            "pulse_width": normalized.get("pulse_width", "0"),
            "frequency":   normalized.get("frequency", "0"),
            "count":       normalized.get("count", "0"),
            "current":     normalized.get("current", "0"),
            "color":       color,
        })

    return params


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
# Phase 0: Initialization
# ─────────────────────────────────────────────
def init_laser(laser: SerialInterface, logger: CommLogger):
    """
    Initialize one laser driver.
    Commands ending with '?' wait for a response before continuing.
    All other commands proceed after cmd_interval delay.
    """
    logger.note(f"=== Phase 0: Initialization ({laser.name}) ===")

    init_cmds = [
        "*IDN?",
        "*CLS",
        "LASER:COND?",
        "LASER:OUTPUT 0",
        "LASER:MODE:IHBW",
        "LASER:RANGE 0",
        "LASER:RANGE?"
        "LASER:LDI 0",
        "LASER:LDI?",
        "LASER:SET:LDI?",
        "LASER:LIM:LDV 4.9",
        "LASER:LIM:LDV?",
        "LASER:LIM:LDI 0",
        "LASER:LIM:LDI?",
        "LASER:OUTPUT 1",
    ]

    for cmd in init_cmds:
        if cmd.endswith("?"):
            laser.send_and_read(cmd)
        else:
            laser.send(cmd)
            time.sleep(CONFIG["cmd_interval"])

    logger.note(f"Initialization complete ({laser.name})")


# ─────────────────────────────────────────────
# Phase 1~n: Run experiment rounds
# ─────────────────────────────────────────────
def phase_run(
    lasers: dict,
    arduino: SerialInterface,
    logger_arduino: CommLogger,
    params: list,
):
    """
    Each round (color selects which laser driver + which Arduino channel is used):
      1. Wait for arduino Ready.  (round 1 waits for power-on Ready., subsequent rounds wait for end-of-round Ready.)
      2. Send LASER:LIM:LDI {current} to the laser driver matching this round's color
      3. Sleep latency seconds
      4. Send {color},{width},{freq},{count} to arduino

    After all rounds: wait for final Ready., then close both lasers.
    """
    total = len(params)

    for idx, p in enumerate(params):
        round_num  = idx + 1
        pulse_width = p["pulse_width"]
        frequency   = p["frequency"]
        count       = p["count"]
        current     = p["current"]
        color       = p["color"]

        laser        = lasers[color]
        logger_laser = laser.logger

        logger_laser.note(f"=== Phase {round_num}: round {round_num}/{total} ({color}) ===")
        logger_arduino.note(f"=== Phase {round_num}: round {round_num}/{total} ({color}) ===")

        # 1. Wait for Ready.
        wait_for_ready(arduino, logger_arduino)

        # 2. Set this round's laser current limit
        laser.send(f"LASER:LIM:LDI {current}")
        time.sleep(CONFIG["cmd_interval"])

        # 3. Fixed latency
        logger_arduino.note(f"Waiting fixed latency {CONFIG['latency']}s ...")
        time.sleep(CONFIG["latency"])

        # 4. Send parameters to arduino (color-prefixed so the board selects the right pin)
        arduino.send(f"{color},{pulse_width},{frequency},{count}")

    # Wait for final round to complete
    logger_arduino.note("=== Waiting for final round to complete ===")
    wait_for_ready(arduino, logger_arduino)

    for color, laser in lasers.items():
        laser.logger.note(f"Waiting {CONFIG['final_wait']}s before closing laser ({color}) ...")
        time.sleep(CONFIG["final_wait"])
        laser.send("LASER:OUTPUT 0")
        laser.logger.note(f"Laser output off ({color}). Experiment complete.")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
def main():
    run_id  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = SCRIPT_DIR / CONFIG["log_dir"] / run_id

    logger_blue    = CommLogger(str(log_dir / "blue_laser_communication.txt"))
    logger_red     = CommLogger(str(log_dir / "red_laser_communication.txt"))
    logger_arduino = CommLogger(str(log_dir / "arduino_communication.txt"))

    params_path = SCRIPT_DIR / CONFIG["params_file"]
    params = load_params(params_path)
    logger_arduino.note(f"Loaded {len(params)} parameter sets from {params_path}")

    blue_laser = SerialInterface("blue_laser", CONFIG["blue_laser_port"], CONFIG["laser_baudrate"], CONFIG["timeout"], logger_blue)
    red_laser  = SerialInterface("red_laser",  CONFIG["red_laser_port"],  CONFIG["laser_baudrate"], CONFIG["timeout"], logger_red)
    arduino    = SerialInterface("arduino",    CONFIG["arduino_port"],    CONFIG["arduino_baudrate"], CONFIG["timeout"], logger_arduino)

    lasers = {"blue": blue_laser, "red": red_laser}

    try:
        for color, laser in lasers.items():
            init_laser(laser, laser.logger)

        phase_run(lasers, arduino, logger_arduino, params)

    except KeyboardInterrupt:
        logger_arduino.note("Interrupted by user.")
        for color, laser in lasers.items():
            laser.logger.note("Interrupted by user. Attempting to close laser...")
            try:
                laser.send("LASER:OUTPUT 0")
            except Exception:
                pass

    except Exception as e:
        logger_arduino.note(f"Error: {e}")
        for color, laser in lasers.items():
            laser.logger.note(f"Error: {e}")
        raise

    finally:
        for color, laser in lasers.items():
            laser.close()
        arduino.close()
        print(f"\nDone. Logs saved to: {log_dir}")


if __name__ == "__main__":
    main()
