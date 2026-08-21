# Laser Power Calibration

## Preparing the Laser with PuTTY

### Connection Setup

1. In the **PuTTY "Session"** panel:

   * Select **Serial** as the connection type
   * Specify the correct **COM port** for the laser driver
   * Set the **Speed (baud rate)** to `38400`

2. In the **"Terminal"** panel:

   * Set **Local echo** to `Force on`
   * Set **Local line editing** to `Force on`

3. Return to the **"Session"** panel and click **Open** to establish the connection.

---

### Configuring the Laser Driver

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

---

## Delivering TTL Signals with the Arduino Board

1. Open the file:

   ```
   laser_calibration.ino
   ```

2. In the **Tools** menu of the Arduino IDE:

   * Set **Board** to `Arduino Mega or Mega 2560`
   * Select the correct **Port** (e.g., `COMx`)

3. Click **Upload** to flash the program to the board.

4. Open the **Serial Monitor** in Arduino IDE.

5. Send commands:

   * `pulse` → generate pulsed signal
   * `steady` → generate continuous signal

6. After calibration, send:

   * `stop` → terminate signal output

---

## Notes on Laser Power Measurement

Due to the physical characteristics of the laser, the output power does not stabilize immediately after activation. Instead, it typically:

* **Overshoots initially**, then
* **Settles to a steady state** over several seconds

For short pulse applications (duration < a few seconds), follow these guidelines:

1. Use the **initial peak power** as the effective output power, since it reflects the actual pulse behavior.

2. Reset the laser current between pulses:

   * Set the current limit to `0` before each activation (`LASER:LIM:LDI 0`)
   * This mimics the real pulse delivery pattern and improves calibration accuracy

---
