import time

import serial

from PumpTasks import PumpTask
from SerialCommands import PhSerialCommand, SerialReply
from dataclasses import dataclass


@dataclass
class PH_Callibration_Data:
    highPH: float
    highMV: float
    lowPH: float
    lowMV: float

class PH_Meter:

    serial_connection = None
    ph_modules = []

    timer = time

    def __init__(self, protocol):
        print("Initialized")

    def initialize_connection(self):
        self.serial_connection = serial.Serial('COM1',
                                          baudrate=19200,
                                          bytesize=serial.EIGHTBITS,
                                          parity=serial.PARITY_NONE,
                                          stopbits=serial.STOPBITS_ONE,
                                          xonxoff=False,
                                          dsrdtr=False,
                                          rtscts=False,
                                          timeout=.5,
                                          )
        # TODO check that the described modules and probes exists.

    def measure_ph_with_probe_associated_with_task(self, current_task: PumpTask):
        return self.measure_ph_with_probe(current_task.ph_meter_id[0], current_task.ph_meter_id[1])

    def measure_ph_with_probe(self, module_id, probe_id) -> float:
        self.send_request_mv_command(module_id)
        mv_response = self.read_mv_result()
        measured_ph_value = self.get_ph_value_from_mv_response(mv_response, probe_id)
        return measured_ph_value

    def get_ph_value_from_mv_response(self, mv_response, probe_id):
        mv_values = self.convert_raw_mv_bin_data_to_mv_values(mv_response.data)
        selected_probe_mv_value = mv_values[int(probe_id) - 1] # From 0 to 3
        ph_value = self.convert_mv_value_to_ph_value(selected_probe_mv_value)
        return ph_value

    def convert_mv_value_to_ph_value(self, mv_value, callibration_data=PH_Callibration_Data(9.0, -114.29, 4, 171.43)):
        ph_slope = (callibration_data.lowPH - callibration_data.highPH)/(callibration_data.lowMV - callibration_data.highMV)
        ph_value = callibration_data.lowPH + (mv_value - callibration_data.lowMV)*ph_slope
        return ph_value

    # mv = milli_volts
    def send_request_mv_command(self, device_ID: str):
        mv_command_id = 10
        mv_command = PhSerialCommand(recipient="M",
                                     length_of_command=6,
                                     command=mv_command_id,
                                     device_id=device_ID,
                                     information_bytes=list())
        self.send_command(mv_command)

    def read_mv_result(self) -> SerialReply:
        self.serial_connection.dtr = False
        recipent = self.serial_connection.read()
        number_of_bytes: bytes = self.serial_connection.read()
        command_acted_upon = self.serial_connection.read()
        reply_device_id = [self. serial_connection.read(), self.serial_connection.read(), self.serial_connection.read(), self.serial_connection.read()]
        length = ord(number_of_bytes)
        data = self.serial_connection.read((length - (1 + 4 + 1)))
        checksum = self.serial_connection.read()
        reply_end = self.serial_connection.read(2)
        reply = SerialReply(recipent, number_of_bytes, command_acted_upon, reply_device_id, data, checksum)
        return reply

    def read_result(self):
        self.serial_connection.dtr = False
        result = self.serial_connection.readline()
        self.serial_connection.read()
        return result

    def send_command(self, command: PhSerialCommand):
        # print(f"Send command: {command.to_binary_command_string()}")
        self.serial_connection.dtr = True
        binary_command = command.to_binary_command_string()
        self.serial_connection.write(binary_command)
        self.timer.sleep(0.5)  # We need to wait for an answer

    def convert_raw_mv_bin_data_to_mv_values(self, raw_data):
        channel_mv_values = []
        if len(raw_data) != 8:
            raise Exception(f"The data given does not contain 8 bytes, but instead {len(raw_data)}")
        for i in range(4):
            # There are two bytes per channel
            byte1 = raw_data[2 * i + 0]
            byte2 = raw_data[2 * i + 1]

            current_channel_mv_value = self.get_mv_value_from_bytes(byte1, byte2)
            channel_mv_values.append(current_channel_mv_value)
        return channel_mv_values

    def get_mv_value_from_bytes(self, byte1, byte2):
        current_channel_value = byte1 * 256 + byte2
        # The ph-meter returns values in two's complement,
        # so if the values are too high, they are actually negative
        if 32767 < current_channel_value:
            current_channel_value -= 65536
        current_channel_mv_value = current_channel_value / 10
        return current_channel_mv_value

    """
    def test_ph_connection(self):
        self.serial_connection.readline()
        self.serial_connection.readline()
        self.serial_connection.readline()
        for module_id in module_ids:
            send_request_mv_command(module_id)
            reply = read_mv_result()
            channel_mv_values = convert_raw_mv_bin_data_to_mv_values(reply.data)
            print(channel_mv_values)
            # In the case that we somehow miss something:
            self.serial_connection.readline()
            self.serial_connection.readline()
    """

