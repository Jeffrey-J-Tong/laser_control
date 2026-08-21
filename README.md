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

Install a Conda-based environment (Miniforge / Miniconda / Anaconda), then run:

```bash
conda create -n com python=3.12
conda activate com
pip install pyserial
```

---

## Scanning Serial Ports

Run [com_scan.py](com_scan.py) to identify available serial ports.

---

## Laser Power Calibration

Manual, interactive calibration is done with PuTTY talking directly to the laser driver, plus an Arduino sketch that outputs steady/pulsed TTL signals for measurement. Use the single-channel tutorial in [laser_calibration_single](laser_calibration_single) or the dual-channel (blue/red) version in [laser_calibration_dual](laser_calibration_dual), depending on your setup.

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

   * Single channel: [laser_calibration_single/laser_calibration_single_mega2560/laser_calibration_mega2560.ino](laser_calibration_single/laser_calibration_single_mega2560/laser_calibration_mega2560.ino)
   * Dual channel: [laser_calibration_dual/laser_calibration_dual_mega2560/laser_calibration_dual_mega2560.ino](laser_calibration_dual/laser_calibration_dual_mega2560/laser_calibration_dual_mega2560.ino)

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

Once calibration is complete, use the automated `laser_control` scripts to run a full pulse-delivery experiment from a CSV parameter table, without manual PuTTY interaction.

**Single channel** — [laser_control_single](laser_control_single):

1. Modify parameters in [laser_control_single/laser_control_protocol_single_mega2560.csv](laser_control_single/laser_control_protocol_single_mega2560.csv)
2. Modify parameters (COM ports, timing) in [laser_control_single/laser_control_single_mega2560.py](laser_control_single/laser_control_single_mega2560.py) if needed
3. Upload [laser_control_single/laser_control_mega2560/laser_control_mega2560.ino](laser_control_single/laser_control_mega2560/laser_control_mega2560.ino) to the Arduino
4. Run `laser_control_single_mega2560.py` in the `com` environment

**Dual channel (blue + red)** — [laser_control_dual](laser_control_dual):

1. Modify parameters in [laser_control_dual/laser_control_protocol_dual_mega2560.csv](laser_control_dual/laser_control_protocol_dual_mega2560.csv) — each row needs a `color` column (`blue` or `red`) selecting which channel and which laser driver that round uses; an extra column (e.g. `note`) can be added freely for your own reference (such as calibrated power), it is ignored by the script
2. Modify parameters (COM ports for the Arduino board and both laser drivers, timing) in [laser_control_dual/laser_control_dual_mega2560.py](laser_control_dual/laser_control_dual_mega2560.py) if needed
3. Upload [laser_control_dual/laser_control_dual_mega2560/laser_control_dual_mega2560.ino](laser_control_dual/laser_control_dual_mega2560/laser_control_dual_mega2560.ino) to the Arduino
4. Run `laser_control_dual_mega2560.py` in the `com` environment
