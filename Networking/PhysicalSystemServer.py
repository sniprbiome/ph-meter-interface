import json
import socket
from io import StringIO
from time import sleep
from typing import Union

import pandas as pd
import yaml
from zmq.backend import Frame
import traceback

import Logger
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

    # The server manages the pumps and proves usde.
    used_pumps = set()
    used_probes = set()
    stop_server = False


    def __init__(self, settings):
        self.settings = settings
        Logger.standardLogger.set_enabled(True)
        Logger.standardLogger.set_logging_path("server_" + self.settings["protocol_path"])
        self.physical_system = PhysicalSystems(settings)

    def connect_to_devices(self):
        self.physical_system.initialize_systems()

    def begin_listening(self):
        self.connect_to_devices()
        socket = self.setup_server_connection()
        self.socket = socket
        print("Begin listening.")
        print()
        while not self.stop_server:
            try:
                client_id = 1234
                encoded_received_message : Union[list[bytes], list[Frame]] = socket.recv_multipart()
                client_id, header, received_message = self.parse_recieved_message(encoded_received_message)
                reply = self.handle_request(header, received_message)
            except Exception as e:
                print("Server side error")
                print(e)
                print(traceback.format_exc())
                Logger.standardLogger.log(e)
                reply = f"ERROR: Server side -> {traceback.format_exc()}"

            #sleep(1)
            print(f"---> Replied ({client_id}): " + reply)
            print()
            reply_encoded = reply.encode()
            socket.send(reply_encoded)

    def parse_recieved_message(self, encoded_received_message):
        received_message = [b.decode() for b in encoded_received_message]
        print(f"Recieved: {encoded_received_message}")
        client_id = received_message[0]
        received_message.pop(0)
        header = received_message[0]
        return client_id, header, received_message

    def handle_request(self, header, received_message):
        if header == "initialize_pumps_used_in_protocol":
            reply = self.initialize_pumps_used_in_protocol(received_message)
        elif header == "get_current_pump_address":
            reply = self.get_current_pump_address()
        elif header == "set_and_get_address_for_current_pump":
            reply = self.set_and_get_address_for_current_pump(received_message)
        elif header == "get_mv_values_of_selected_probes":
            reply = self.get_mv_values_of_selected_probes(received_message)
        elif header == "measure_ph_with_probe_associated_with_task":
            reply = self.measure_ph_with_probe_associated_with_task(received_message)
        elif header == "get_ph_values_of_selected_probes":
            reply = self.get_ph_values_of_selected_probes(received_message)
        elif header == "recalibrate_ph_meter":
            reply = self.recalibrate_ph_meter()
        elif header == "set_pump_dose_multiplication_factor":
            reply = self.set_pump_dose_multiplication_factor(received_message)
        elif header == "pump_n_times":
            reply = self.pump_n_times(received_message)
        elif header == "disconnect":
            reply = self.disconnect(received_message)
        elif header == "test":
            reply = "test answer"
        elif header == "stop":
            reply = "Stopping"
        else:
            reply = f"ERROR: Header has invalid format: {header}"
        return reply

    def disconnect(self, received_message):
        protocol_json = received_message[1]
        protocol = pd.read_json(StringIO(protocol_json))
        # Disconnect the used pumps and probes:
        protocol_rows = [row for index, row in protocol.iterrows()]
        protocol_pumps = set([row["Pump"] for row in protocol_rows])
        protocol_probes = set([row["pH probe"] for row in protocol_rows])
        self.used_pumps = self.used_pumps - protocol_pumps
        self.used_probes = self.used_probes - protocol_probes
        reply = "Done"
        return reply

    def pump_n_times(self, received_message):
        pump_id = received_message[1]
        pump_multiplier = int(received_message[2])
        self.physical_system.pump_n_times(pump_id, pump_multiplier)
        reply = "Done"
        return reply

    def set_pump_dose_multiplication_factor(self, received_message):
        protocol = pd.read_json(StringIO(received_message[1]))
        dose_multiplication_factor = int(received_message[2])
        self.physical_system.set_pump_dose_multiplication_factor(protocol, dose_multiplication_factor)
        reply = "Done"
        return reply

    def recalibrate_ph_meter(self):
        self.physical_system.recalibrate_ph_meter()
        reply = "Done"
        return reply

    def get_ph_values_of_selected_probes(self, received_message):
        selected_probes = json.loads(received_message[1])
        ph_values = self.physical_system.get_ph_values_of_selected_probes(selected_probes)
        reply = json.dumps(ph_values)
        return reply

    def measure_ph_with_probe_associated_with_task(self, received_message):
        probe_id = received_message[1]
        ph = self.physical_system.ph_meter.measure_ph_with_probe(probe_id)
        reply = str(ph)
        return reply

    def get_mv_values_of_selected_probes(self, received_message):
        selected_probes = json.loads(received_message[1])
        mv_values = self.physical_system.get_mv_values_of_selected_probes(selected_probes)
        reply = json.dumps(mv_values)
        return reply

    def set_and_get_address_for_current_pump(self, received_message):
        address = int(received_message[1])
        reply_address = self.physical_system.set_and_get_address_for_current_pump(address)
        reply = reply_address
        return reply

    def get_current_pump_address(self):
        pump_address = self.physical_system.get_current_pump_address()
        reply = str(pump_address)
        return reply

    def initialize_pumps_used_in_protocol(self, received_message):
        protocol_json = received_message[1]
        protocol = pd.read_json(StringIO(protocol_json))
        # It also needs to manage the used pumps and probes:
        protocol_rows = [row for index, row in protocol.iterrows()]
        protocol_pumps = set([row["Pump"] for row in protocol_rows])
        protocol_probes = set([row["pH probe"] for row in protocol_rows])
        if protocol_pumps & self.used_pumps:
            reply = f"Note: Currently, the following pumps are being used {self.used_pumps}," \
                    f" and the protocol uses the following pumps {protocol_pumps}"
        elif protocol_probes & self.used_probes:
            reply = f"Note: Currently, the following pH probes are being used {self.used_probes}," \
                    f" and the protocol uses the following pumps {protocol_probes}"
        else:
            self.used_pumps = protocol_pumps.union(self.used_pumps)
            self.used_probes = protocol_probes.union(self.used_probes)
            self.physical_system.initialize_pumps_used_in_protocol(protocol)
            reply = "Done"
        return reply

    def stop(self):
        self.socket.close()
        self.context.term()

    def setup_server_connection(self):
        print("Establishing server.")
        context = zmq.Context()
        self.context = context
        server_connection_socket = context.socket(zmq.REP)
        server_connection_socket.bind(ADDRESS)
        return server_connection_socket
