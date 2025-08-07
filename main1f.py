#!/usr/bin/env python3
"""
Main script for the DMX Controller Project.
Coordinates GUI, DMX communication, effects, sensors, scenes, LEDs, IR, audio, OSC, and sequences.
Now integrates head objects (MH110Head, StageWashHead).
"""
import sys
import threading
import time
import logging
from PyQt5.QtWidgets import (QApplication, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QPushButton, QComboBox, QSpinBox, QTextEdit, QFileDialog)
from PyQt5.QtCore import Qt, QTimer
from backend import dmx, effects, sensors, scenes, leds, ir, audio, osc, sequences
from backend.heads.mh110_head import MH110Head
from backend.heads.stagewash_head import StageWashHead

# Configure logging
logging.basicConfig(
    filename='logs/dmx_controller.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DMXControllerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DMX Controller Ultimate")
        self.dmx = dmx.DMXSender()
        self.start_address = 1
        self.mode_channels = 14  # Default to StageWashHead
        self.head_objects = []
        self.effect_thread = None
        self.sequence_thread = None
        self.running = True
        self.current_sequence = None
        self.init_ui()
        self.init_heads()
        self.init_timers()
        self.start_threads()
        logging.info("Application initialized")

    def init_ui(self):
        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.manual_tab(), "Manual")
        self.tabs.addTab(self.color_tab(), "Colors")
        self.tabs.addTab(self.effects_tab(), "Effects")
        self.tabs.addTab(self.scenes_tab(), "Scenes")
        self.tabs.addTab(self.view_tab(), "View/Sensor")
        self.tabs.addTab(self.sequences_tab(), "Sequences")
        layout.addWidget(self.tabs)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(QLabel("Logs:"))
        layout.addWidget(self.log_view)
        self.setLayout(layout)

    def init_heads(self):
        self.head_objects = []
        for i in range(2):  # Example with 2 heads
            addr = self.start_address + i * self.mode_channels
            self.head_objects.append(StageWashHead(addr))
        self.log(f"Initialized {len(self.head_objects)} heads")

    def manual_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        self.sliders = {}
        self.slider_layout = QVBoxLayout()
        for head_index, head in enumerate(self.head_objects):
            for ch in range(self.mode_channels):
                h_layout = QHBoxLayout()
                lbl = QLabel(f"H{head_index+1}-CH{ch+1}")
                slider = QSlider(Qt.Horizontal)
                slider.setRange(0, 255)
                slider.valueChanged.connect(lambda val, h=head_index, c=ch: self.update_dmx(h, c, val))
                h_layout.addWidget(lbl)
                h_layout.addWidget(slider)
                self.sliders[(head_index, ch)] = slider
                self.slider_layout.addLayout(h_layout)
        layout.addLayout(self.slider_layout)
        btn_blackout = QPushButton("Blackout")
        btn_blackout.clicked.connect(self.blackout)
        layout.addWidget(btn_blackout)
        tab.setLayout(layout)
        return tab

    def color_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        btn = QPushButton("Select Color")
        btn.clicked.connect(self.pick_color)
        layout.addWidget(btn)
        tab.setLayout(layout)
        return tab

    def effects_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        for effect in ["ColorChase", "Strobe", "Rainbow", "AudioReactivity"]:
            btn = QPushButton(f"Start {effect}")
            btn.clicked.connect(lambda _, e=effect: self.run_effect(e))
            layout.addWidget(btn)
        btn_stop = QPushButton("Stop Effect")
        btn_stop.clicked.connect(self.stop_effect)
        layout.addWidget(btn_stop)
        tab.setLayout(layout)
        return tab

    def scenes_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        btn_save = QPushButton("Save Scene")
        btn_save.clicked.connect(self.save_scene)
        btn_load = QPushButton("Load Scene")
        btn_load.clicked.connect(self.load_scene)
        layout.addWidget(btn_save)
        layout.addWidget(btn_load)
        tab.setLayout(layout)
        return tab

    def view_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        self.sensor_combo = QComboBox()
        self.sensor_combo.addItems(["DHT11", "DHT22"])
        layout.addWidget(QLabel("Sensor:"))
        layout.addWidget(self.sensor_combo)
        self.sensor_label = QLabel("Temp: -- °C  Hum: -- %")
        layout.addWidget(self.sensor_label)
        tab.setLayout(layout)
        return tab

    def sequences_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        btn_load = QPushButton("Load Sequence")
        btn_load.clicked.connect(self.load_sequence)
        btn_run = QPushButton("Run Sequence")
        btn_run.clicked.connect(self.run_sequence)
        btn_stop = QPushButton("Stop Sequence")
        btn_stop.clicked.connect(self.stop_sequence)
        layout.addWidget(btn_load)
        layout.addWidget(btn_run)
        layout.addWidget(btn_stop)
        tab.setLayout(layout)
        return tab

    def init_timers(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_sensor)
        self.timer.start(1000)

    def start_threads(self):
        threading.Thread(target=self.dmx.send_loop, daemon=True).start()
        threading.Thread(target=self.read_sensors, daemon=True).start()
        threading.Thread(target=self.monitor_ir, daemon=True).start()
        threading.Thread(target=osc.start_osc_server, args=(self.dmx,), daemon=True).start()

    def update_dmx(self, head_index, channel, value):
        addr = self.start_address - 1 + head_index * self.mode_channels + channel
        self.dmx.update_channel(addr, value)
        self.log(f"DMX channel {addr+1} set to {value}")

    def blackout(self):
        for head_index in range(len(self.head_objects)):
            for ch in range(self.mode_channels):
                addr = self.start_address - 1 + head_index * self.mode_channels + ch
                self.dmx.update_channel(addr, 0)
        self.log("Blackout activated")

    def pick_color(self):
        from PyQt5.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid():
            for head in self.head_objects:
                head.set_rgb(self.dmx.dmx_data, color.red(), color.green(), color.blue(), 0)
            self.log(f"Color applied: {color.name()}")

    def run_effect(self, name):
        if name == "AudioReactivity":
            self.effect_thread = threading.Thread(
                target=audio.run_audio_reactivity,
                args=(self.dmx, self.start_address, len(self.head_objects), self.mode_channels),
                daemon=True)
        else:
            self.effect_thread = threading.Thread(
                target=effects.run_effect,
                args=(name, self.dmx, self.start_address, len(self.head_objects), self.mode_channels),
                daemon=True)
        self.effect_thread.start()
        self.log(f"Effect {name} started")
        leds.set_led_color(0, 0, 1)

    def stop_effect(self):
        effects.stop_effect()
        audio.stop_audio_reactivity()
        self.log("Effect stopped")
        leds.set_led_color(0, 1, 0)

    def save_scene(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Scene", filter="JSON Files (*.json)")
        if path:
            scenes.save_scene(self.dmx.dmx_data, path)
            self.log(f"Scene saved: {path}")

    def load_scene(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Scene", filter="JSON Files (*.json)")
        if path:
            data = scenes.load_scene(path)
            for i, value in enumerate(data):
                self.dmx.update_channel(i, value)
            self.log(f"Scene loaded: {path}")

    def load_sequence(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Sequence", filter="JSON Files (*.json)")
        if path:
            self.current_sequence = sequences.load_sequence(path)
            self.log(f"Sequence loaded: {path}")

    def run_sequence(self):
        if self.current_sequence:
            self.sequence_thread = threading.Thread(
                target=sequences.run_sequence,
                args=(self.dmx, self.start_address, len(self.head_objects), self.mode_channels, self.current_sequence),
                daemon=True)
            self.sequence_thread.start()
            self.log("Sequence started")

    def stop_sequence(self):
        sequences.stop_sequence()
        self.log("Sequence stopped")

    def read_sensors(self):
        while self.running:
            humidity, temperature = sensors.read_dht(self.sensor_combo.currentText())
            if humidity is not None and temperature is not None:
                self.sensor_label.setText(f"Temp: {temperature:.1f}°C  Hum: {humidity:.1f}%")
            time.sleep(1)

    def monitor_ir(self):
        while self.running:
            if ir.is_ir_detected():
                self.run_effect("ColorChase")
                leds.set_led_color(0, 0, 1)
            else:
                leds.set_led_color(0, 1, 0)
            time.sleep(0.1)

    def update_sensor(self):
        pass

    def log(self, msg):
        self.log_view.append(f"{time.strftime('%H:%M:%S')} - {msg}")
        logging.info(msg)

    def closeEvent(self, event):
        self.running = False
        self.dmx.stop()
        osc.stop_osc_server()
        sequences.stop_sequence()
        leds.cleanup()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = DMXControllerApp()
    controller.resize(1000, 700)
    controller.show()
    sys.exit(app.exec_())
