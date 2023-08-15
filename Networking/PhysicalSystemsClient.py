import json
import time

import pandas as pd
import yaml

import ast
import Logger
import PumpTasks
from PhMeter import PhMeter
from PhysicalSystemsInterface import PhysicalSystemsInterface
from PumpSystem import PumpSystem

from abc import ABC, abstractmethod

import zmq

from Networking import PhysicalSystemServer
from PhysicalSystems import PhysicalSystems
import Scheduler

# Now working through message passing!
class PhysicalSystemsClient(PhysicalSystemsInterface):

    def __init__(self, settings):
        self.settings = settings

    #Establishes connection with server
    def initialize_systems(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(PhysicalSystemServer.ADDRESS)
        print("Connection with server established.")

    def send_and_receive(self, message: list[str]) -> str:
        encoded_message = [s.encode() for s in message]
        self.socket.send_multipart(encoded_message)
        #  Get the reply.
        encoded_reply: bytes = self.socket.recv()
        reply = encoded_reply.decode()
        print(f"Received reply [ {reply} ]")
        if reply == "ERROR":
            e = Exception(reply)
            Logger.standardLogger.log(e)
            raise e
        return reply

    def initialize_pumps_used_in_protocol(self, protocol: pd.DataFrame) -> None:
        self.send_and_receive(["initialize_pumps_used_in_protocol", protocol.to_json()])
        #self.pump_system.setup_pumps_used_in_protocol(protocol)

    def get_current_pump_address(self) -> bytes:
        # Assumes the pump system has been initialized.
        pump_address_string = self.send_and_receive(["get_current_pump_address"])
        pump_address = pump_address_string.encode()
        return pump_address

    def set_and_get_address_for_current_pump(self, address: int) -> bytes:
        actual_address_string = self.send_and_receive(["set_and_get_address_for_current_pump", str(address)])
        actual_address = actual_address_string.encode()
        return actual_address

    def pump(self, pump_id: str) -> None:
        self.send_and_receive(["pump", pump_id])

    # Ph
    def get_mv_values_of_selected_probes(self, selected_probes: list[str]) -> dict[str, float]:
        mv_values_json = self.send_and_receive(["get_mv_values_of_selected_probes", json.dumps(selected_probes)])
        mv_values = json.loads(mv_values_json)
        return mv_values

    def measure_ph_with_probe_associated_with_task(self, current_task: PumpTasks) -> float:
        probe_id = f"{current_task.ph_meter_id[0]}_{current_task.ph_meter_id[1]}"
        ph_string = self.send_and_receive(["measure_ph_with_probe_associated_with_task", probe_id])
        ph = float(ph_string)
        return ph

    def get_ph_values_of_selected_probes(self, ph_probes: list[str]) -> dict[str, float]:
        ph_values_json = self.send_and_receive(["get_ph_values_of_selected_probes", json.dumps(ph_probes)])
        ph_values = json.loads(ph_values_json)
        return ph_values

    def recalibrate_ph_meter(self) -> None:
        self.send_and_receive(["recalibrate_ph_meter"])

    def set_pump_dose_multiplication_factor(self, protocol: pd.DataFrame, dose_multiplication_factor) -> None:
        self.send_and_receive(["set_pump_dose_multiplication_factor", protocol.to_json, str(dose_multiplication_factor)])

    def pump_n_times(self, pump_id: int, pump_multiplier: int) -> None:
        self.send_and_receive(["pump_n_times", str(pump_id), str(pump_multiplier)])


if __name__ == "__main__":
    client = PhysicalSystemsClient(None)
    client.initialize_pumps_used_in_protocol(Scheduler.select_instruction_sheet("../Minigut.setup_FD.xlsx"))
