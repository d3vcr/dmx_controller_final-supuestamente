#!/usr/bin/env python3
"""
Main script for the DMX Controller Project.
Coordinates the GUI, DMX communication, effects, sensors, scenes, LEDs, IR, audio, OSC, and sequences.
"""
import sys
import threading
import time
import logging
from PyQt5.QtWidgets import QApplication, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QComboBox, QSpinBox, QTextEdit, QFileDialog
from PyQt5.QtCore import Qt, QTimer
from backend import dmx, effects, sensors, scenes, leds, ir, audio, osc, sequences

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
        self.dmx = dmx.DMXSender()  # Initialize DMX communication
        self.start_address = 1
        self.mode_channels = 9
        self.heads = 2
        self.effect_thread = None
        self.sequence_thread = None
        self.running = True
        self.current_sequence = None
        self.init_ui()
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

        # Log panel
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(QLabel("Logs:"))
        layout.addWidget(self.log_view)
        self.setLayout(layout)
        self.log("UI initialized")

    def manual_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        # Configuration: mode, address, heads
        h_conf = QHBoxLayout()
        h_conf.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["9CH", "14CH"])
        self.mode_combo.currentIndexChanged.connect(self.change_mode)
        h_conf.addWidget(self.mode_combo)

        h_conf.addWidget(QLabel("Start Address:"))
        self.addr_spin = QSpinBox()
        self.addr_spin.setRange(1, 512)
        self.addr_spin.valueChanged.connect(self.change_address)
        h_conf.addWidget(self.addr_spin)

        h_conf.addWidget(QLabel("Heads:"))
        self.heads_spin = QSpinBox()
        self.heads_spin.setRange(1, 10)
        self.heads_spin.valueChanged.connect(self.change_heads)
        h_conf.addWidget(self.heads_spin)
        layout.addLayout(h_conf)

        # Sliders for each head and channel
        self.sliders = {}
        self.slider_layout = QVBoxLayout()
        self.create_controls()
        layout.addLayout(self.slider_layout)

        # Buttons
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
        for effect in ["ColorChase", "Strobe", "Rainbow", "GoboPattern", "AudioReactivity"]:
            btn = QPushButton(f"Start {effect}")
            btn.clicked.connect(lambda _, e=effect: self.run_effect(e))
            layout.addWidget(btn)
        btn_stop = QPushButton("Stop Effect")
        btn_stop.clicked.connect(self.stop_effect)
        layout.addWidget(btn_stop)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 100)
        self.speed_slider.setValue(100)
        self.speed_slider.valueChanged.connect(self.update_effect_speed)
        layout.addWidget(QLabel("Effect Speed"))
        layout.addWidget(self.speed_slider)
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
        h_s = QHBoxLayout()
        h_s.addWidget(QLabel("Sensor:"))
        self.sensor_combo = QComboBox()
        self.sensor_combo.addItems(["DHT11", "DHT22"])
        h_s.addWidget(self.sensor_combo)
        layout.addLayout(h_s)
        self.sensor_label = QLabel("Temp: --°C  Hum: --%")
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
        self.dmx_thread = threading.Thread(target=self.dmx.send_loop, daemon=True)
        self.dmx_thread.start()
        self.sensor_thread = threading.Thread(target=self.read_sensors, daemon=True)
        self.sensor_thread.start()
        self.ir_thread = threading.Thread(target=self.monitor_ir, daemon=True)
        self.ir_thread.start()
        self.osc_thread = threading.Thread(target=osc.start_osc_server, args=(self.dmx,), daemon=True)
        self.osc_thread.start()
        logging.info("Threads started: DMX, Sensor, IR, OSC")

    def create_controls(self):
        # Clear existing sliders
        for i in reversed(range(self.slider_layout.count())):
            self.slider_layout.itemAt(i).widget().deleteLater()
        self.sliders = {}
        for head in range(self.heads):
            for ch in range(self.mode_channels):
                h_layout = QHBoxLayout()
                lbl = QLabel(f"H{head+1}-CH{ch+1}")
                slider = QSlider(Qt.Horizontal)
                slider.setRange(0, 255)
                slider.valueChanged.connect(lambda val, h=head, c=ch: self.update_dmx(h, c, val))
                h_layout.addWidget(lbl)
                h_layout.addWidget(slider)
                self.sliders[(head, ch)] = slider
                self.slider_layout.addLayout(h_layout)
        self.log(f"Controls created: {self.heads} heads x {self.mode_channels} channels")

    def change_mode(self, index):
        self.mode_channels = 9 if index == 0 else 14
        self.create_controls()
        self.log(f"Changed to {self.mode_channels}CH mode")

    def change_address(self, value):
        self.start_address = value
        self.log(f"Start address set to d{str(value).zfill(3)}")

    def change_heads(self, value):
        self.heads = value
        self.create_controls()
        self.log(f"Number of heads set to {self.heads}")

    def update_dmx(self, head, channel, value):
        addr = self.start_address - 1 + head * self.mode_channels + channel
        self.dmx.update_channel(addr, value)
        self.log(f"DMX channel {addr+1} set to {value}")

    def blackout(self):
        for head in range(self.heads):
            for ch in range(self.mode_channels):
                addr = self.start_address - 1 + head * self.mode_channels + ch
                self.dmx.update_channel(addr, 0)
        self.log("Blackout activated")

    def pick_color(self):
        from PyQt5.QtGui import QColor
        from PyQt5.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid():
            for head in range(self.heads):
                base = self.start_address - 1 + head * self.mode_channels
                r_idx = base + (3 if self.mode_channels == 9 else 6)
                g_idx = r_idx + 1
                b_idx = r_idx + 2
                self.dmx.update_channel(r_idx, color.red())
                self.dmx.update_channel(g_idx, color.green())
                self.dmx.update_channel(b_idx, color.blue())
            self.log(f"Color applied: {color.name()}")

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
            self.create_controls()
            self.log(f"Scene loaded: {path}")

    def run_effect(self, name):
        if self.effect_thread and self.effect_thread.is_alive():
            self.log("Another effect is running")
            return
        if name == "AudioReactivity":
            self.effect_thread = threading.Thread(
                target=lambda: audio.run_audio_reactivity(
                    self.dmx, self.start_address, self.heads, self.mode_channels
                ),
                daemon=True
            )
        else:
            self.effect_thread = threading.Thread(
                target=lambda: effects.run_effect(name, self.dmx, self.start_address, self.heads, self.mode_channels),
                daemon=True
            )
        self.effect_thread.start()
        self.log(f"Effect {name} started")
        leds.set_led_color(0, 0, 1)  # Blue LED for effect

    def stop_effect(self):
        effects.stop_effect()
        audio.stop_audio_reactivity()
        self.effect_thread = None
        self.log("Effect stopped")
        leds.set_led_color(0, 1, 0)  # Green LED for idle

    def update_effect_speed(self, value):
        effects.effect_manager.set_speed(value)
        self.log(f"Effect speed set to {value}%")

    def load_sequence(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Sequence", filter="JSON Files (*.json)")
        if path:
            self.current_sequence = sequences.load_sequence(path)
            self.log(f"Sequence loaded: {path}")

    def run_sequence(self):
        if hasattr(self, 'current_sequence') and self.current_sequence:
            if self.sequence_thread and self.sequence_thread.is_alive():
                self.log("Another sequence is running")
                return
            self.sequence_thread = threading.Thread(
                target=lambda: sequences.run_sequence(
                    self.dmx, self.start_address, self.heads, self.mode_channels, self.current_sequence
                ),
                daemon=True
            )
            self.sequence_thread.start()
            self.log("Sequence started")
            leds.set_led_color(0, 0, 1)  # Blue LED for sequence
        else:
            self.log("No sequence loaded")

    def stop_sequence(self):
        sequences.stop_sequence()
        self.sequence_thread = None
        self.log("Sequence stopped")
        leds.set_led_color(0, 1, 0)  # Green LED for idle

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
                leds.set_led_color(0, 0, 1)  # Blue LED when IR detected
            else:
                leds.set_led_color(0, 1, 0)  # Green LED when idle
            time.sleep(0.1)

    def update_sensor(self):
        pass  # Handled by sensor thread

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
