import time
from typing import List

import pandas as pd
import serial

from PumpTasks import PumpTask
from SerialCommands import PhSerialCommand, SerialReply
from dataclasses import dataclass

@dataclass
class PhCalibrationData:
    highPH: float
    highMV: float
    lowPH: float
    lowMV: float


class PhReadException(Exception):
    pass


class PhMeter:

    serial_connection = None
    timer = time

    def __init__(self, ph_meter_settings: dict, probe_calibration_data: dict[str, dict[str, int]]) -> None:
        self.settings = ph_meter_settings
        self.probe_calibration_data = probe_calibration_data

    def initialize_connection(self) -> None:
        self.serial_connection = serial.Serial(f'COM{self.settings["ComPort"]}',
                                               baudrate=19200,
                                               bytesize=serial.EIGHTBITS,
                                               parity=serial.PARITY_NONE,
                                               stopbits=serial.STOPBITS_ONE,
                                               xonxoff=False,
                                               dsrdtr=False,
                                               rtscts=False,
                                               timeout=.5,
                                               )
        self.serial_connection.read_all()  # Remove some extra bytes

    def disconnect(self):
        self.serial_connection.close()

    def measure_ph_with_probe_associated_with_task(self, current_task: PumpTask) -> float:
        measured_ph = self.measure_ph_with_probe(f"{current_task.ph_meter_id[0]}_{current_task.ph_meter_id[1]}")
        return measured_ph

    def measure_ph_with_probe(self, probe_id: str) -> float:
        try:
            mv_response = self.get_mv_values_of_module(probe_id.split("_")[0])
        except:
            # Something might be wrong with the serial connection, so it will try to measure again,
            # and otherwise the calling program must handle the error.
            mv_response = self.get_mv_values_of_module(probe_id.split("_")[0])
        if self.settings["ShouldPrintPhMeterMessages"]:
            print(f"Returned mv response: {mv_response}")
        measured_ph_value = self.get_ph_value_of_probe_from_mv_response(mv_response, probe_id)
        return measured_ph_value

    def get_mv_values_of_module(self, module_id: str) -> SerialReply:
        self.send_request_mv_command(module_id)
        mv_response = self.read_mv_result()
        return mv_response

    def get_ph_value_of_probe_from_mv_response(self, mv_response: SerialReply, probe_id: str) -> float:
        selected_probe_mv_value = self.get_mv_values_of_probe(mv_response, probe_id)
        ph_value = self.convert_mv_value_to_ph_value(selected_probe_mv_value, probe_id)
        return ph_value

    def get_mv_values_of_probe(self, mv_response: SerialReply, probe_id: str) -> float:
        mv_values = self.convert_raw_mv_bin_data_to_mv_values(mv_response.data)
        selected_probe_mv_value = mv_values[int(probe_id.split("_")[1]) - 1]  # From 0 to 3
        return selected_probe_mv_value

    def convert_mv_value_to_ph_value(self, mv_value: float, probe_id: str) -> float:
        probe_calibration = self.probe_calibration_data[probe_id]
        ph_slope = (probe_calibration["LowPH"] - probe_calibration["HighPH"]) / \
                   (probe_calibration["LowPHmV"] - probe_calibration["HighPHmV"])
        ph_value = probe_calibration["LowPH"] + (mv_value - probe_calibration["LowPHmV"]) * ph_slope
        return ph_value

    # mv = milli_volts
    def send_request_mv_command(self, device_ID: str) -> None:
        mv_command_id = 10
        mv_command = PhSerialCommand(recipient="M",
                                     length_of_command=6,
                                     command=mv_command_id,
                                     device_id=device_ID,
                                     information_bytes=list())
        self.send_command(mv_command)

    def read_mv_result(self) -> SerialReply:
        try:
            self.serial_connection.dtr = False
            recipient = self.serial_connection.read()
            number_of_bytes: bytes = self.serial_connection.read()
            command_acted_upon = self.serial_connection.read()
            reply_device_id = [self. serial_connection.read(), self.serial_connection.read(),
                               self.serial_connection.read(), self.serial_connection.read()]
            length = ord(number_of_bytes)
            data = self.serial_connection.read((length - (1 + 4 + 1)))
            checksum = self.serial_connection.read()
            reply_end = self.serial_connection.read(2)
            extra_reply = self.serial_connection.read_all()  # Sometimes it contains an extra \x00
            if not(extra_reply == b'\x00' or extra_reply == b''):
                print(f"Error when measuring ph. Got the following extra data as a reply: {extra_reply}")
            reply = SerialReply(recipient, number_of_bytes, command_acted_upon, reply_device_id, data, checksum)
        except Exception:
            raise PhReadException()
        return reply

    def read_result(self) -> bytes:
        self.serial_connection.dtr = False
        result = self.serial_connection.readline()
        self.serial_connection.read()
        return result

    def send_command(self, command: PhSerialCommand) -> None:
        self.serial_connection.dtr = True
        binary_command = command.to_binary_command_string()
        self.serial_connection.write(binary_command)
        if self.settings["ShouldPrintPhMeterMessages"]:
            print(f"Send ph command: {binary_command}")
        self.timer.sleep(1)  # We need to wait for an answer

    def convert_raw_mv_bin_data_to_mv_values(self, raw_data: bytes) -> List[float]:
        channel_mv_values = []
        if len(raw_data) != 8:
            raise Exception(f"The data given does not contain 8 bytes, but instead {len(raw_data)}, namely: {raw_data}")
        for i in range(4):
            # There are two bytes per channel
            byte1 = raw_data[2 * i + 0]
            byte2 = raw_data[2 * i + 1]

            current_channel_mv_value = self.get_mv_value_from_bytes(byte1, byte2)
            channel_mv_values.append(current_channel_mv_value)
        return channel_mv_values

    def get_mv_value_from_bytes(self, byte1: int, byte2: int) -> float:
        current_channel_value = byte1 * 256 + byte2
        # The ph-meter returns values in two's complement,
        # so if the values are too high, they are actually negative
        if 32767 < current_channel_value:
            current_channel_value -= 65536
        current_channel_mv_value = current_channel_value / 10  # The units are in 0.1 mv
        return current_channel_mv_value

    def update_calibration_data(self, ph_probe_calibration_data):
        self.probe_calibration_data = ph_probe_calibration_data

    def get_ph_value_of_selected_probes(self, selected_probes: list[str]) -> dict[str, float]:
        mv_values = self.get_mv_values_of_selected_probes(selected_probes)
        ph_values = dict()
        for probe in selected_probes:
            mv_value = mv_values[probe]
            ph_values[probe] = self.convert_mv_value_to_ph_value(mv_value, probe)
        return ph_values

    def get_mv_values_of_selected_probes(self, selected_probes: list[str]) -> dict[str, float]:
        modules_used = set(map(lambda probe: probe.split("_")[0], selected_probes))

        all_probe_to_mv_values = {}
        # We first record all the module values, and then select values of interest amongst those.
        # This is done to speed things up.

        for module in modules_used:
            try:
                # This might fail due to an error with the signal etc.
                module_mv_response = self.get_mv_values_of_module(module)
            except PhReadException:
                # wait a second and try to measure again
                time.sleep(1)
                module_mv_response = self.get_mv_values_of_module(module)

            all_probe_to_mv_values[module + "_1"] = self.get_mv_values_of_probe(module_mv_response, module + "_1")
            all_probe_to_mv_values[module + "_2"] = self.get_mv_values_of_probe(module_mv_response, module + "_2")
            all_probe_to_mv_values[module + "_3"] = self.get_mv_values_of_probe(module_mv_response, module + "_3")
            all_probe_to_mv_values[module + "_4"] = self.get_mv_values_of_probe(module_mv_response, module + "_4")

        probe_to_mv_value = {probe: all_probe_to_mv_values[probe] for probe in selected_probes}

        return probe_to_mv_value
