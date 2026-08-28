# Setting Up a Laser System with an Arduino Board

## Software Requirements

Before getting started, make sure the following software is installed:

1. **Serial port debugging tool**: PuTTY
2. **Arduino development environment**: Arduino IDE (for running `.ino` scripts)
3. **Python environment**: Miniforge / Miniconda / Anaconda
4. **Python development tools**: VS Code with Python extension
5. **USB driver** for Arroyo 4220-DR LaserSource

---

## Connecting the Arroyo 4220-DR LaserSource

1. Connect the laser source to your computer via a USB port.
2. Install the required USB driver:

   * [Download USB Driver](https://www.arroyoinstruments.com/wp-content/uploads/2020/12/ArroyoUSBDrivers.zip)
   * [Product Page (Reference)](https://www.arroyoinstruments.com/product/4220-dr-lasersource-1a-2a/)
3. After installation, verify that the device appears in the system's **Device Manager**.

For a **dual-channel (blue + red)** setup, repeat the steps above for the second Arroyo 4220-DR unit — each channel uses its own laser driver on its own COM port.

---

## Connecting the Arduino Board

1. Connect the **Arduino Mega 2560** to your computer via USB.

2. Wire the Arduino to the laser source:

   * **Single channel**: connect **Pin 8** and **GND** to the laser source BNC port using a Dupont-to-BNC adapter cable.
   * **Dual channel**: connect **Pin 8** (BLUE) and **Pin 9** (RED), each with its own **GND**, to their respective laser source BNC ports.
   * Ensure correct polarity for each channel:

     * BNC positive terminal → signal pin (Pin 8 or Pin 9)
     * BNC negative terminal → GND
   * (Optional) Use a **BNC splitter**, or a hardware line splitter, if synchronization with other devices (e.g. a data-acquisition system) is required — this avoids any timing skew that sequential `digitalWrite()` calls to separate pins would introduce.

3. Configure the Arduino IDE:

   * Go to **Tools → Board → Arduino AVR Boards → Arduino Mega or Mega 2560**
   * Select the correct **COM port** under **Tools → Port**

---

## Preparing the Python Environment

Install a Conda-based environment (Miniforge / Miniconda / Anaconda), then install this repo as an editable package (this pulls in `pyserial` automatically and sets up the `laser-control-*` commands used below):

```bash
conda create -n com python=3.12
conda activate com
cd laser_control          # repo root, where pyproject.toml lives
pip install -e .
```

---

## Scanning Serial Ports

Run `laser-control-scan` to list all currently connected serial ports (device, description, manufacturer, VID/PID), so you can tell which COM port is which before editing a config file.

---

## Laser Power Calibration

Manual, interactive calibration is done with PuTTY talking directly to the laser driver, plus an Arduino sketch that outputs steady/pulsed TTL signals for measurement. Use the single-channel sketch in [firmware/laser_calibration_single_mega2560](firmware/laser_calibration_single_mega2560) or the dual-channel (blue/red) version in [firmware/laser_calibration_dual_mega2560](firmware/laser_calibration_dual_mega2560), depending on your setup.

### Preparing the Laser with PuTTY

#### Connection Setup

1. In the **PuTTY "Session"** panel:

   * Select **Serial** as the connection type
   * Specify the correct **COM port** for the laser driver
   * Set the **Speed (baud rate)** to `38400`

2. In the **"Terminal"** panel:

   * Set **Local echo** to `Force on`
   * Set **Local line editing** to `Force on`

3. Return to the **"Session"** panel and click **Open** to establish the connection.

#### Configuring the Laser Driver

Run the following commands in PuTTY to initialize and configure the laser driver:

```text
*IDN?
*CLS
LASER:COND?
LASER:MODE:IHBW
LASER:LDI?
LASER:LIM:LDV 4.9
LASER:LIM:LDV?
LASER:LIM:LDI 500
LASER:OUTPUT 1
LASER:LDI 0
LASER:LDI?
```

To adjust the calibration, modify the current limit using:

```text
LASER:LIM:LDI <value>
```

Once configured, the laser driver is ready for **TTL control**.

After completing calibration, turn off the output and clear the status:

```text
LASER:OUTPUT 0
*CLS
```

### Delivering TTL Signals with the Arduino Board

1. Open the calibration sketch in the Arduino IDE:

   * Single channel: [firmware/laser_calibration_single_mega2560/laser_calibration_single_mega2560.ino](firmware/laser_calibration_single_mega2560/laser_calibration_single_mega2560.ino)
   * Dual channel: [firmware/laser_calibration_dual_mega2560/laser_calibration_dual_mega2560.ino](firmware/laser_calibration_dual_mega2560/laser_calibration_dual_mega2560.ino)

2. In the **Tools** menu of the Arduino IDE:

   * Set **Board** to `Arduino Mega or Mega 2560`
   * Select the correct **Port** (e.g., `COMx`)

3. Click **Upload** to flash the program to the board.

4. Open the **Serial Monitor** in Arduino IDE.

5. Send commands:

   * Dual channel only: send `red` or `blue` first to select which channel the next commands apply to
   * `steady` → generate continuous signal
   * `pulse` → generate pulsed signal

6. After calibration, send:

   * `stop` → terminate signal output (dual channel: only stops the currently selected channel)

### Notes on Laser Power Measurement

Due to the physical characteristics of the laser, the output power does not stabilize immediately after activation. Instead, it typically:

* **Overshoots initially**, then
* **Settles to a steady state** over several seconds

For short pulse applications (duration < a few seconds), follow these guidelines:

1. Use the **initial peak power** as the effective output power, since it reflects the actual pulse behavior.

2. Reset the laser current between pulses:

   * Set the current limit to `0` before each activation (`LASER:LIM:LDI 0`)
   * This mimics the real pulse delivery pattern and improves calibration accuracy

---

## Laser Pulse Delivery

Once calibration is complete, use the `laser-control-single` / `laser-control-dual` commands (installed via `pip install -e .`, see [Preparing the Python Environment](#preparing-the-python-environment)) to run a full pulse-delivery experiment from a CSV parameter table, without manual PuTTY interaction.

Serial ports, baud rates, and timing (`cmd_interval`, `latency`, `final_wait`) are **not** hardcoded — they live in a TOML config file:

* [configs/laser_control_single_config.toml](configs/laser_control_single_config.toml)
* [configs/laser_control_dual_config.toml](configs/laser_control_dual_config.toml)

Edit the relevant file to match your COM ports before running (use `laser-control-scan` to find them). To use a different config file entirely (e.g. a second bench setup), pass `--config path\to\other_config.toml`.

**Single channel**:

1. Modify parameters in a protocol CSV (e.g. the bundled [protocols/laser_control_protocol_single_mega2560.csv](protocols/laser_control_protocol_single_mega2560.csv), or your own copy) — `pulse_width`, `frequency`, `count`, `current` must all be positive integers; extra columns (e.g. `note`) are ignored and safe to add for your own reference
2. Upload [firmware/laser_control_single_mega2560/laser_control_single_mega2560.ino](firmware/laser_control_single_mega2560/laser_control_single_mega2560.ino) to the Arduino
3. Run:
   ```bash
   laser-control-single "path\to\your_protocol.csv"
   ```
   Omitting the path falls back to the bundled default protocol file, after a `[y/N]` confirmation prompt.

**Dual channel (blue + red)**:

1. Modify parameters in a protocol CSV (e.g. the bundled [protocols/laser_control_protocol_dual_mega2560.csv](protocols/laser_control_protocol_dual_mega2560.csv)) — same required columns as above, plus a `color` column (`blue` or `red`) selecting which channel and which laser driver that round uses
2. Upload [firmware/laser_control_dual_mega2560/laser_control_dual_mega2560.ino](firmware/laser_control_dual_mega2560/laser_control_dual_mega2560.ino) to the Arduino
3. Run:
   ```bash
   laser-control-dual "path\to\your_protocol.csv"
   ```

Every row of the protocol file is validated (positive integers, valid `color` for the dual version) **before** any serial port is opened — if something is wrong, all problem rows are reported together so you can fix the CSV in one pass.

Logs for each run are written to `logs/<timestamp>/` under the directory you ran the command from (not the repo).
