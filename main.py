import time
from socket import timeout
import serial
from dataclasses import dataclass
from typing import *

from SerialCommands import SerialCommand, SerialReply


module_ids = ["F.0.1.13", "F.0.1.21", "F.0.1.22"]

ph = serial.Serial('COM1',
                   baudrate=19200,
                   bytesize=serial.EIGHTBITS,
                   parity=serial.PARITY_NONE,
                   stopbits=serial.STOPBITS_ONE,
                   xonxoff=False,
                   dsrdtr=False,
                   rtscts=False,
                   timeout=.5,
                   )


def send_request_mv_command(device_ID: str):
    mv_command_id = 10
    mv_command = SerialCommand(recipient="M",
                               length_of_command=6,
                               command=mv_command_id,
                               device_id=device_ID,
                               information_bytes=list())
    send_command(mv_command)




def read_mv_result() -> SerialReply:

    ph.dtr = False
    recipent = ph.read()
    number_of_bytes : bytes = ph.read()
    command_acted_upon = ph.read()
    reply_device_id = [ph.read(), ph.read(), ph.read(), ph.read()]
    length = ord(number_of_bytes)
    data = ph.read((length - (1+4+1)))
    checksum = ph.read()
    reply_end = ph.read(2)
    reply = SerialReply(recipent, number_of_bytes, command_acted_upon, reply_device_id, data, checksum)
    print(f"Has read mv result: {reply}")
    return reply

def read_result():
    ph.dtr = False
    result = ph.readline()
    print(f"Read result: {result}")
    ph.read()
    return result

def send_command(command: SerialCommand):
    print(f"Send command: {command.to_binary_command_string()}")
    ph.dtr = True
    binary_command = command.to_binary_command_string()
    ph.write(binary_command)
    time.sleep(0.2)  # We need to wait for an answer

def main():

    ph.readline()
    ph.readline()
    ph.readline()

    for module_id in module_ids:
        send_request_mv_command(module_id)
        reply = read_mv_result()
        channel_mv_values = convert_raw_mv_bin_data_to_mv_values(reply.data)
        print(channel_mv_values)
        # In the case that we somehow miss something:
        ph.readline()
        ph.readline()

    # start_program_select_instruction_sheet()


def convert_raw_mv_bin_data_to_mv_values(raw_data):
    channel_mv_values = []
    for i in range(4):
        # There are two bytes per channel
        byte1 = raw_data[2 * i + 0]
        byte2 = raw_data[2 * i + 1]

        current_channel_mv_value = get_mv_value_from_bytes(byte1, byte2)
        channel_mv_values.append(current_channel_mv_value)
    return channel_mv_values


def get_mv_value_from_bytes(byte1, byte2):
    current_channel_value = byte1 * 256 + byte2
    # The ph-meter returns values in two's complement,
    # so if the values are too high, they are actually negative
    if 32767 < current_channel_value:
        current_channel_value -= 65536
    current_channel_mv_value = current_channel_value / 10
    return current_channel_mv_value


if __name__ == "__main__":
    main()
