"""
Laser Controller (Dual Channel)
================================
Controls two laser drivers (blue + red) and a single dual-channel Arduino
board's serial communication sequentially. The Arduino board runs the
dual-channel laser_control firmware (see firmware/laser_control_dual_mega2560/),
which drives BLUE on PIN8 and RED on PIN9, one pulse train at a time.

Installed as the `laser-control-dual` command (pip install -e .).

Usage:
    laser-control-dual [protocol_file] [--config CONFIG_TOML]

    protocol_file   Path to the protocol CSV file (each row needs a "color"
                     column, blue/red). If omitted, the bundled default under
                     protocols/ is used after a y/N confirmation.
    --config        Path to a TOML config file overriding the bundled default
                     (configs/laser_control_dual_config.toml). See that file
                     for the available keys (COM ports, baud rates, timing).

Log output: <log_dir>/<timestamp>/blue_laser_communication.txt
            <log_dir>/<timestamp>/red_laser_communication.txt
            <log_dir>/<timestamp>/arduino_communication.txt
            (log_dir is relative to the current working directory; see the
            config file's "log_dir" key)
"""

import argparse
import time
from pathlib import Path

from laser_control.common import (
    CommLogger,
    SerialInterface,
    wait_for_ready,
    resolve_protocol_path,
    confirm_default_protocol,
    load_config,
    new_run_log_dir,
    read_csv_rows,
    positive_int,
    raise_if_errors,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "laser_control_dual_config.toml"
DEFAULT_PROTOCOL_PATH = REPO_ROOT / "protocols" / "laser_control_protocol_dual_mega2560.csv"

DEFAULTS = {
    "blue_laser_port":  "COM5",
    "red_laser_port":   "COM6",
    "arduino_port":     "COM4",
    "laser_baudrate":   38400,
    "arduino_baudrate": 115200,
    "timeout":          5.0,
    "cmd_interval":     0.1,
    "latency":          20.0,
    "final_wait":       1.0,
    "log_dir":          "logs",
}


# ─────────────────────────────────────────────
# Parameter file
# ─────────────────────────────────────────────
def load_params(filepath: Path) -> list:
    """
    Read and validate the protocol CSV file. Every row must include a
    'color' column (blue/red, case-insensitive) selecting which channel and
    which laser driver that round uses. Every row is checked before any
    serial port is opened; if any row is invalid, all problems are reported
    together (row number, column, offending value) instead of stopping at
    the first one.
    """
    rows = read_csv_rows(filepath)

    params = []
    errors = []
    for i, row in enumerate(rows, start=2):  # header is line 1
        entry = {}
        for col in ("pulse_width", "frequency", "count", "current"):
            raw = row.get(col, "")
            try:
                entry[col] = positive_int(raw)
            except (TypeError, ValueError):
                errors.append(f"row {i}: column '{col}' = {raw!r} must be a positive integer")

        color = row.get("color", "").strip().lower()
        if color not in ("blue", "red"):
            errors.append(f"row {i}: column 'color' = {row.get('color', '')!r} must be 'blue' or 'red'")
        entry["color"] = color

        params.append(entry)

    raise_if_errors(errors, filepath)
    return params


# ─────────────────────────────────────────────
# Phase 0: Initialization
# ─────────────────────────────────────────────
def init_laser(laser: SerialInterface, logger: CommLogger, cfg: dict):
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
        "LASER:RANGE?",
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
            time.sleep(cfg["cmd_interval"])

    logger.note(f"Initialization complete ({laser.name})")


# ─────────────────────────────────────────────
# Phase 1~n: Run experiment rounds
# ─────────────────────────────────────────────
def phase_run(
    lasers: dict,
    arduino: SerialInterface,
    logger_arduino: CommLogger,
    params: list,
    cfg: dict,
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
        time.sleep(cfg["cmd_interval"])

        # 3. Fixed latency
        logger_arduino.note(f"Waiting fixed latency {cfg['latency']}s ...")
        time.sleep(cfg["latency"])

        # 4. Send parameters to arduino (color-prefixed so the board selects the right pin)
        arduino.send(f"{color},{pulse_width},{frequency},{count}")

    # Wait for final round to complete
    logger_arduino.note("=== Waiting for final round to complete ===")
    wait_for_ready(arduino, logger_arduino)

    for color, laser in lasers.items():
        laser.logger.note(f"Waiting {cfg['final_wait']}s before closing laser ({color}) ...")
        time.sleep(cfg["final_wait"])
        laser.send("LASER:OUTPUT 0")
        laser.logger.note(f"Laser output off ({color}). Experiment complete.")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="laser-control-dual",
        description="Run a dual-channel (blue+red) laser pulse-delivery experiment from a protocol CSV file.",
    )
    parser.add_argument(
        "protocol_file",
        nargs="?",
        default=None,
        help="Path to the protocol CSV file (each row needs a 'color' column). "
             "If omitted, the bundled default under protocols/ is used after a y/N confirmation.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a TOML config file overriding the bundled default "
             "(configs/laser_control_dual_config.toml).",
    )
    return parser


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
def main():
    args = build_arg_parser().parse_args()

    if args.protocol_file:
        params_path = resolve_protocol_path(args.protocol_file)
    else:
        params_path = confirm_default_protocol(DEFAULT_PROTOCOL_PATH)

    config_path = Path(args.config).resolve() if args.config else DEFAULT_CONFIG_PATH
    cfg = load_config(config_path, DEFAULTS)

    params = load_params(params_path)

    log_dir = new_run_log_dir(Path.cwd() / cfg["log_dir"])

    logger_blue    = CommLogger(str(log_dir / "blue_laser_communication.txt"))
    logger_red     = CommLogger(str(log_dir / "red_laser_communication.txt"))
    logger_arduino = CommLogger(str(log_dir / "arduino_communication.txt"))

    logger_arduino.note(f"Loaded {len(params)} parameter sets from {params_path}")
    logger_arduino.note(f"Using config: {config_path}")

    blue_laser = SerialInterface("blue_laser", cfg["blue_laser_port"], cfg["laser_baudrate"], cfg["timeout"], logger_blue)
    red_laser  = SerialInterface("red_laser",  cfg["red_laser_port"],  cfg["laser_baudrate"], cfg["timeout"], logger_red)
    arduino    = SerialInterface("arduino",    cfg["arduino_port"],    cfg["arduino_baudrate"], cfg["timeout"], logger_arduino)

    lasers = {"blue": blue_laser, "red": red_laser}

    try:
        for color, laser in lasers.items():
            init_laser(laser, laser.logger, cfg)

        phase_run(lasers, arduino, logger_arduino, params, cfg)

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
            laser.logger.note("Attempting to close laser output...")
            try:
                laser.send("LASER:OUTPUT 0")
            except Exception:
                pass
        raise

    finally:
        for color, laser in lasers.items():
            laser.close()
        arduino.close()
        print(f"\nDone. Logs saved to: {log_dir}")


if __name__ == "__main__":
    main()
