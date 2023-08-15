import json
import socket
from io import StringIO
from time import sleep

import pandas as pd
import yaml

from PhysicalSystems import PhysicalSystems

import sys
import selectors
import types


import zmq

HOST = "127.0.0.1"
DEFAULT_PORT = 5555
ADDRESS = f"tcp://{HOST}:{DEFAULT_PORT}"


def load_settings(settings_path):
    with open(settings_path, 'r') as file:
        return yaml.safe_load(file)


def split_message(received_message: str):
    split_message = received_message.split(b" ", 1)
    header = split_message[0]
    message = split_message[1]
    return header, message


class PhysicalSystemServer:

    def __init__(self, settings):
        self.physical_system = PhysicalSystems(settings)

    def begin_listening(self):
        socket = self.setup_server_connection()
        print("Begin listening.")
        while True:
            encoded_received_message = socket.recv_multipart()
            received_message = [b.decode() for b in encoded_received_message]
            print(f"Recieved: {received_message}")
            header = received_message[0]
            if header == "initialize_pumps_used_in_protocol":
                protocol_json = received_message[1]
                protocol = pd.read_json(StringIO(protocol_json))
                self.physical_system.initialize_pumps_used_in_protocol(protocol)
                reply = "Done"
            elif header == "get_current_pump_address":
                pump_address = self.physical_system.get_current_pump_address()
                reply = str(pump_address)
            elif header == "set_and_get_address_for_current_pump":
                address = int(received_message[1])
                reply_address = self.physical_system.set_and_get_address_for_current_pump(address)
                reply = reply_address
            elif header == "get_mv_values_of_selected_probes":
                selected_probes = received_message[1]
                mv_values = self.physical_system.get_mv_values_of_selected_probes(selected_probes)
                reply = json.dumps(mv_values)
            elif header == "measure_ph_with_probe_associated_with_task":
                probe_id = received_message[1]
                ph = self.physical_system.ph_meter.measure_ph_with_probe(probe_id)
                reply = str(ph)
            elif header == "get_ph_values_of_selected_probes":
                selected_probes = received_message[1]
                ph_values = self.physical_system.get_mv_values_of_selected_probes(selected_probes)
                reply = json.dumps(ph_values)
            elif header == "recalibrate_ph_meter":
                self.physical_system.recalibrate_ph_meter()
                reply = "Done"
            elif header == "set_pump_dose_multiplication_factor":
                protocol = pd.read_json(StringIO(received_message[1]))
                dose_multiplication_factor = int(received_message[2])
                self.physical_system.set_pump_dose_multiplication_factor(protocol, dose_multiplication_factor)
                reply = "Done"
            elif header == "pump_n_times":
                pump_id = received_message[1]
                pump_multiplier = int(received_message[2])
                self.physical_system.pump_n_times(pump_id, pump_multiplier)
                reply = "Done"
            else:
                reply = "ERROR"

            #sleep(1)
            print("---> Replied: " + reply)
            reply_encoded = reply.encode()
            socket.send(reply_encoded)

    def setup_server_connection(self):
        print("Establishing server.")
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind(ADDRESS)
        return socket


if __name__ == "__main__":
    server = PhysicalSystemServer()
