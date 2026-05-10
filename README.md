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

---

## Connecting the Arduino Board

1. Connect the **Arduino Mega 2560** to your computer via USB.

2. Wire the Arduino to the laser source:

   * Connect **Pin 8** and **GND** to the laser source BNC port using a Dupont-to-BNC adapter cable.
   * Ensure correct polarity:

     * BNC positive terminal → **Pin 8**
     * BNC negative terminal → **GND**
   * (Optional) Use a **BNC splitter** if synchronization with other devices is required.

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

Run `com_scan.py` to identify available serial ports.

---

## Laser Power Calibration

Refer to the tutorial in the `laser_calibration` directory.

---

## Laser Pulse Delivery

1. Modify parameters in `laser_control/laser_protocol.csv`

2. Modify parameters in `laser_control/laser_control.py` if needed

3. Upload the Arduino script: `laser_control/laser_control.ino` (ensure the correct board is selected if multiple devices are connected.)

4. Run the `laser_control/laser_control.py` in the `com` environment:
