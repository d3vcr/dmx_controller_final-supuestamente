"""
DMX communication module using MAX485.
Handles sending DMX data to moving heads.
"""

import serial
import threading
import time
import logging

class DMXSender:
    def __init__(self, port='/dev/ttyS0', baudrate=250000, num_channels=512):
        self.serial = serial.Serial(port, baudrate=baudrate, stopbits=serial.STOPBITS_TWO)
        self.lock = threading.Lock()
        self.dmx_data = bytearray([0] * num_channels)
        self.running = False
        logging.info(f"DMXSender initialized on {port}")

    def update_channel(self, addr, value):
        with self.lock:
            if 0 <= addr < len(self.dmx_data):
                self.dmx_data[addr] = max(0, min(255, value))

    def send_loop(self, interval=0.023):  # ~44 Hz refresh rate
        while self.running:
            with self.lock:
                packet = bytearray([0]) + self.dmx_data
                self.serial.break_condition = True
                time.sleep(0.0001)  # Break time
                self.serial.break_condition = False
                self.serial.write(packet)
            time.sleep(interval)

    def start(self):
        self.running = True
        threading.Thread(target=self.send_loop, daemon=True).start()

    def stop(self):
        self.running = False
