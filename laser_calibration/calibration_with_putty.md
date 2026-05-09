# Calibration with putty

## Prepare laser with putty

### Connect

1. In putty `Session` page:
    1. select serial port, specify the COM port for the laser driver
    2. set the `Speed` (bout rate) to 38400
2. In `Terminal` page:

    set the `Local echo` and `Local line editing` to `Force on`
3. Go back to `Session` page, click `open`

### Set laser driver status with commands

``` text
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

To modify and calibre, change the number in this command:

```text
LASER:LIM:LDI x
```

Now the laser driver is ready for TTL control.

After finishing calibration, type command:

``` text
LASER:OUTPUT 0
*CLS
```

## Deliver TTL signal with Arduino board

1. Open `laser_calibration.ino`
2. In the `Tools` toggle panel
    1. specify `Board`: `Arduino Mega or Mega 2560`
    2. specify `Port`: `COMx`
3. Press `Upload`
4. Open `Serial Monitor` in Arduino IDE
5. Type `pulse` or `steady`
6. Type `stop` after finishing calibration
