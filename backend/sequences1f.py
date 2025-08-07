"""
Sequences module for DMX moving heads using head classes.
Supports loading and running complex sequences with effect and DMX steps.
"""

import time
import json
import logging
from backend import effects

class SequenceManager:
    def __init__(self):
        self.running = False
        self.current_sequence = None

    def run_sequence(self, dmx_sender, head_objects, sequence):
        self.running = True
        self.current_sequence = sequence
        try:
            for step in sequence:
                if not self.running:
                    break

                # Run effect step
                if "effect" in step:
                    effects.run_effect(step["effect"], dmx_sender, head_objects)
                    time.sleep(step.get("duration", 1))
                    effects.stop_effect()

                # Run manual DMX step (per head)
                elif "dmx" in step:
                    for head_index, channel_values in step["dmx"].items():
                        head_index = int(head_index)
                        head = head_objects[head_index]
                        for attr, val in channel_values.items():
                            if hasattr(head, attr):
                                getattr(head, attr)(dmx_sender.dmx_data, val)
                            else:
                                logging.warning(f"Head {head_index} has no method {attr}")
                    time.sleep(step.get("duration", 1))

                logging.info(f"Sequence step: {step}")
        except Exception as e:
            logging.error(f"Sequence error: {e}")

    def stop(self):
        self.running = False
        self.current_sequence = None

    def load_sequence(self, path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading sequence: {e}")
            return []

sequence_manager = SequenceManager()

def run_sequence(dmx_sender, head_objects, sequence):
    sequence_manager.run_sequence(dmx_sender, head_objects, sequence)

def stop_sequence():
    sequence_manager.stop()

def load_sequence(path):
    return sequence_manager.load_sequence(path)
