from pathlib import Path
import time
import serial

deadline = time.monotonic() + 240
with serial.Serial("COM14", 115200, timeout=0.2) as port:
    with Path(__file__).with_name("uart.log").open("wb") as output:
        while time.monotonic() < deadline:
            data = port.read(port.in_waiting or 1)
            if data:
                output.write(data)
                output.flush()
                print(data.decode("ascii", errors="replace"), end="", flush=True)
