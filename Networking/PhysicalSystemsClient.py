import json
import random
from multiprocessing import Process

import pandas as pd
import Logger
import PumpTasks
from PhysicalSystemsInterface import PhysicalSystemsInterface
import zmq

from Networking import PhysicalSystemServer

# Now working through message passing!
class PhysicalSystemsClient(PhysicalSystemsInterface):

    client_id = random.randint(0, 100)

    def __init__(self, settings):
        self.settings = settings
        context = zmq.Context()
        self.client_socket = context.socket(zmq.REQ)

    #Establishes connection with server
    def initialize_systems(self):
        self.client_socket.connect(PhysicalSystemServer.ADDRESS)
        print("Connection with server established.")

    def send_and_receive(self, message: list[str]) -> str:
        try:
            message.insert(0, str(self.client_id))
            encoded_message = [s.encode() for s in message]
            if self.settings["networking"]["ShouldPrintSendRecieveMessages"]:
                print(f"\nSending message: {encoded_message}")
            self.client_socket.send_multipart(encoded_message)
            #  Get the reply.
            encoded_reply: bytes = self.client_socket.recv()
            reply = encoded_reply.decode()
        except Exception as e:
            Logger.standardLogger.log(e)
            raise e

        if self.settings["networking"]["ShouldPrintSendRecieveMessages"]:
            print(f"Received reply ({self.client_id}) [ {reply} ]")

        if reply.startswith("ERROR"):
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

    def disconnect(self, protocol: pd.DataFrame) -> None:
        self.send_and_receive(["disconnect", protocol.to_json()])