"""
Effects module for DMX moving heads.
Supports ColorChase, Strobe, and Rainbow effects using head classes.
"""

import threading
import time
import colorsys
import logging
from backend.heads.mh110_head import MH110Head
from backend.heads.stagewash_head import StageWashHead

class EffectManager:
    def __init__(self):
        self.current_effect = None
        self.running = False
        self.speed = 100  # Default speed %
        self.heads = []

    def run_effect(self, name, dmx_sender, head_objects):
        self.running = True
        self.current_effect = name
        self.heads = head_objects
        if name == "ColorChase":
            self.color_chase(dmx_sender)
        elif name == "Strobe":
            self.strobe(dmx_sender)
        elif name == "Rainbow":
            self.rainbow(dmx_sender)
        logging.info(f"Effect {name} finished")

    def stop_effect(self):
        self.running = False
        self.current_effect = None

    def set_speed(self, value):
        self.speed = value

    def color_chase(self, dmx_sender):
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        while self.running and self.current_effect == "ColorChase":
            for color in colors:
                for head in self.heads:
                    if hasattr(head, "set_rgb"):
                        head.set_rgb(dmx_sender.dmx_data, *color)
                    elif hasattr(head, "set_rgbw"):
                        head.set_rgbw(dmx_sender.dmx_data, *color, 0)
                time.sleep(max(0.05, 1.0 - self.speed / 100.0))

    def strobe(self, dmx_sender):
        on = False
        while self.running and self.current_effect == "Strobe":
            val = 255 if on else 0
            for head in self.heads:
                if hasattr(head, "set_strobe"):
                    head.set_strobe(dmx_sender.dmx_data, val)
            on = not on
            time.sleep(max(0.02, 0.5 - self.speed / 200.0))

    def rainbow(self, dmx_sender):
        hue = 0.0
        while self.running and self.current_effect == "Rainbow":
            r, g, b = [int(x * 255) for x in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
            for head in self.heads:
                if hasattr(head, "set_rgb"):
                    head.set_rgb(dmx_sender.dmx_data, r, g, b)
                elif hasattr(head, "set_rgbw"):
                    head.set_rgbw(dmx_sender.dmx_data, r, g, b, 0)
            hue = (hue + 0.01) % 1.0
            time.sleep(max(0.02, 0.2 - self.speed / 200.0))

effect_manager = EffectManager()

def run_effect(name, dmx_sender, head_objects):
    effect_manager.run_effect(name, dmx_sender, head_objects)

def stop_effect():
    effect_manager.stop_effect()

def set_speed(value):
    effect_manager.set_speed(value)
