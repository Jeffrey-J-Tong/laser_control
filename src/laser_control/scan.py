"""
List all currently connected serial ports and their descriptions, so you can
tell which COM port corresponds to which device (Arduino, laser driver, ...)
before editing a config file.

Installed as the `laser-control-scan` command (pip install -e .).
"""


def main():
    import serial.tools.list_ports

    for p in serial.tools.list_ports.comports():
        print(p.device, "|", p.description, "|", p.manufacturer, "|", p.vid, p.pid)


if __name__ == "__main__":
    main()
