"""
Laser Controller (Single Channel)
==================================
Controls a laser driver and an Arduino Mega 2560 board's serial
communication sequentially. The Arduino board runs the single-channel
laser_control firmware (see firmware/laser_control_single_mega2560/).

Installed as the `laser-control-single` command (pip install -e .).

Usage:
    laser-control-single [protocol_file] [--config CONFIG_TOML]

    protocol_file   Path to the protocol CSV file. If omitted, the bundled
                     default under protocols/ is used after a y/N confirmation.
    --config        Path to a TOML config file overriding the bundled default
                     (configs/laser_control_single_config.toml). See that file
                     for the available keys (COM ports, baud rates, timing).

Log output: <log_dir>/<timestamp>/laser_communication.txt
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
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "laser_control_single_config.toml"
DEFAULT_PROTOCOL_PATH = REPO_ROOT / "protocols" / "laser_control_protocol_single_mega2560.csv"

DEFAULTS = {
    "laser_port":       "COM3",
    "arduino_port":     "COM4",
    "laser_baudrate":   38400,
    "arduino_baudrate": 115200,
    "timeout":          5.0,
    "cmd_interval":     0.1,
    "latency":          5.0,
    "final_wait":       1.0,
    "log_dir":          "logs",
}


# ─────────────────────────────────────────────
# Parameter file
# ─────────────────────────────────────────────
def load_params(filepath: Path) -> list:
    """
    Read and validate the protocol CSV file. Every row is checked before any
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
        params.append(entry)

    raise_if_errors(errors, filepath)
    return params


# ─────────────────────────────────────────────
# Phase 0: Initialization
# ─────────────────────────────────────────────
def phase_init(laser: SerialInterface, logger: CommLogger, cfg: dict):
    """
    Initialize laser driver.
    Commands ending with '?' wait for a response before continuing.
    All other commands proceed after cmd_interval delay.
    """
    logger.note("=== Phase 0: Initialization ===")

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

    logger.note("Initialization complete")


# ─────────────────────────────────────────────
# Phase 1~n: Run experiment rounds
# ─────────────────────────────────────────────
def phase_run(
    laser: SerialInterface,
    arduino: SerialInterface,
    logger_laser: CommLogger,
    logger_arduino: CommLogger,
    params: list,
    cfg: dict,
):
    """
    Each round:
      1. Wait for arduino Ready.  (round 1 waits for power-on Ready., subsequent rounds wait for end-of-round Ready.)
      2. Send LASER:LIM:LDI {current} to laser driver
      3. Sleep latency seconds
      4. Send {width},{freq},{count} to arduino

    After all rounds: wait for final Ready., then close laser.
    """
    total = len(params)

    for idx, p in enumerate(params):
        round_num = idx + 1
        pulse_width = p["pulse_width"]
        frequency   = p["frequency"]
        count       = p["count"]
        current     = p["current"]

        logger_laser.note(f"=== Phase {round_num}: round {round_num}/{total} ===")
        logger_arduino.note(f"=== Phase {round_num}: round {round_num}/{total} ===")

        # 1. Wait for Ready.
        wait_for_ready(arduino, logger_arduino)

        # 2. Set laser current limit
        laser.send(f"LASER:LIM:LDI {current}")
        time.sleep(cfg["cmd_interval"])

        # 3. Fixed latency
        logger_arduino.note(f"Waiting fixed latency {cfg['latency']}s ...")
        time.sleep(cfg["latency"])

        # 4. Send parameters to arduino
        arduino.send(f"{pulse_width},{frequency},{count}")

    # Wait for final round to complete
    logger_arduino.note("=== Waiting for final round to complete ===")
    wait_for_ready(arduino, logger_arduino)

    logger_laser.note(f"Waiting {cfg['final_wait']}s before closing laser ...")
    time.sleep(cfg["final_wait"])
    laser.send("LASER:OUTPUT 0")
    logger_laser.note("Laser output off. Experiment complete.")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="laser-control-single",
        description="Run a single-channel laser pulse-delivery experiment from a protocol CSV file.",
    )
    parser.add_argument(
        "protocol_file",
        nargs="?",
        default=None,
        help="Path to the protocol CSV file. If omitted, the bundled default "
             "under protocols/ is used after a y/N confirmation.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a TOML config file overriding the bundled default "
             "(configs/laser_control_single_config.toml).",
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

    logger_laser   = CommLogger(str(log_dir / "laser_communication.txt"))
    logger_arduino = CommLogger(str(log_dir / "arduino_communication.txt"))

    logger_laser.note(f"Loaded {len(params)} parameter sets from {params_path}")
    logger_arduino.note(f"Loaded {len(params)} parameter sets from {params_path}")
    logger_laser.note(f"Using config: {config_path}")

    laser   = SerialInterface("laser",   cfg["laser_port"],   cfg["laser_baudrate"],   cfg["timeout"], logger_laser)
    arduino = SerialInterface("arduino", cfg["arduino_port"], cfg["arduino_baudrate"], cfg["timeout"], logger_arduino)

    try:
        phase_init(laser, logger_laser, cfg)
        phase_run(laser, arduino, logger_laser, logger_arduino, params, cfg)

    except KeyboardInterrupt:
        logger_laser.note("Interrupted by user. Attempting to close laser...")
        logger_arduino.note("Interrupted by user.")
        try:
            laser.send("LASER:OUTPUT 0")
        except Exception:
            pass

    except Exception as e:
        logger_laser.note(f"Error: {e}")
        logger_arduino.note(f"Error: {e}")
        logger_laser.note("Attempting to close laser output...")
        try:
            laser.send("LASER:OUTPUT 0")
        except Exception:
            pass
        raise

    finally:
        laser.close()
        arduino.close()
        print(f"\nDone. Logs saved to: {log_dir}")


if __name__ == "__main__":
    main()
