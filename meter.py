"""Read a PulseAudio monitor and drive the Speaker pHAT SN3218.

Register protocol and LED wiring references:
https://github.com/pimoroni/sn3218-python
https://github.com/pimoroni/speaker-phat/blob/master/python/speakerphat.py
"""

import array
import fcntl
import json
import logging
import math
import os
import selectors
import signal
import subprocess
import sys
import threading

LOG = logging.getLogger("speaker-phat-vu")
CHANNELS = (0, 1, 2, 4, 6, 8, 10, 12, 14, 16)
STOP = threading.Event()
RATE = 16000
FRAME_BYTES = 640  # 20 ms of signed 16-bit mono samples


def led_values(count, brightness, reverse=False):
    values = [0] * 18
    mapping = CHANNELS[::-1] if reverse else CHANNELS
    for channel in mapping[:max(0, min(10, count))]:
        values[channel] = brightness
    return values


class LEDs:
    def __init__(self):
        self.fd = os.open("/dev/i2c-1", os.O_RDWR)
        try:
            fcntl.ioctl(self.fd, 0x0703, 0x54)  # I2C_SLAVE, not FORCE
            self.write(0x00, [0])
            self.display([0] * 18)
            mask = sum(1 << channel for channel in CHANNELS)
            self.write(0x13, [(mask >> shift) & 0x3F for shift in (0, 6, 12)])
            self.write(0x16, [0xFF])
            self.write(0x00, [1])
        except BaseException:
            os.close(self.fd)
            raise

    def write(self, register, values):
        data = bytes([register, *values])
        if os.write(self.fd, data) != len(data):
            raise OSError("Incomplete I2C write")

    def display(self, values):
        self.write(0x01, values)
        self.write(0x16, [0xFF])

    def close(self):
        try:
            self.display([0] * 18)
            self.write(0x00, [0])
        finally:
            os.close(self.fd)


def rms_level(frame):
    samples = array.array("h")
    samples.frombytes(frame)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return 0.0
    return math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768


def bar_count(level, floor_db, gain_db):
    db = 20 * math.log10(max(level, 1e-12)) + gain_db
    return max(0, min(10, math.ceil((db - floor_db) * 10 / -floor_db)))


def log_sources():
    result = subprocess.run(
        ["pactl", "list", "short", "sources"], capture_output=True,
        text=True, timeout=10, check=True,
    )
    LOG.info("Available PulseAudio sources (choose the pHAT .monitor):\n%s", result.stdout)


def monitor(leds, options):
    source = options["source"]
    LOG.info("Monitoring %s", source)
    command = [
        "parec", "--raw", "--format=s16le", f"--rate={RATE}",
        "--channels=1", "--latency-msec=40", f"--device={source}",
        "--client-name=Speaker pHAT VU Meter",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    pending = bytearray()
    envelope = 0.0
    last_count = None
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while not STOP.is_set():
                if not selector.select(timeout=0.25):
                    # A suspended output may stop supplying samples.
                    leds.display([0] * 18)
                    envelope = 0.0
                    last_count = 0
                    if process.poll() is not None:
                        raise RuntimeError(f"parec exited: {process.returncode}")
                    continue
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    raise RuntimeError("PulseAudio monitor disconnected")
                pending.extend(chunk)
                while len(pending) >= FRAME_BYTES:
                    level = rms_level(pending[:FRAME_BYTES])
                    del pending[:FRAME_BYTES]
                    envelope = max(level, envelope * 0.86)
                    count = bar_count(envelope, options["floor_db"], options["gain_db"])
                    if count != last_count:
                        leds.display(led_values(count, options["brightness"], options["reverse"]))
                        last_count = count
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdout.close()
        leds.display([0] * 18)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: STOP.set())
    with open("/data/options.json", encoding="utf-8") as file:
        options = json.load(file)
    leds = LEDs()
    try:
        if options["startup_test"]:
            LOG.info("Testing the ten LEDs")
            mapping = CHANNELS[::-1] if options["reverse"] else CHANNELS
            for channel in mapping:
                if STOP.is_set():
                    break
                values = [0] * 18
                values[channel] = options["brightness"]
                leds.display(values)
                STOP.wait(0.15)
            leds.display([0] * 18)
        while not STOP.is_set():
            try:
                log_sources()
                monitor(leds, options)
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                leds.display([0] * 18)
                LOG.error("%s; retrying in 5 seconds", error)
                STOP.wait(5)
    finally:
        leds.close()


if __name__ == "__main__":
    main()
