import time
from socket import timeout
import serial
from dataclasses import dataclass
from typing import *

from SerialCommands import SerialCommand, SerialReply

device = [ord('M')]
device_id = [15, 0, 1, 34]
request_rackID = [2, 5]
request_mV = [6, 10]
line_end = [13, 10]
start_stop = [255]

ph = serial.Serial('COM1',
                   baudrate=19200,
                   bytesize=serial.EIGHTBITS,
                   parity=serial.PARITY_NONE,
                   stopbits=serial.STOPBITS_ONE,
                   xonxoff=False,
                   dsrdtr=False,
                   rtscts=False,
                   timeout=1,
                   )


def get_checksum(command: list) -> list:
    return sum(command)

def generate_command_string(command: list) -> str:
    output = ""
    for i in command:
        output += chr(i)
    return output

def send_request_mv_command(device_ID: str):
    mv_command_id = 10
    mv_command = SerialCommand(recipient="M",
                               length_of_command=6,
                               command=mv_command_id,
                               device_id=device_ID,
                               information_bytes=list())
    send_command(mv_command)

def device_ID_string_to_hex_ID(device_ID):
    device_ID_split = device_ID.split(".")
    device_ID_hex = list(map(lambda x : int(x, 16), device_ID_split))
    return device_ID_hex





def send_command(command: SerialCommand):
    print(f"Send command: {command.to_binary_command_string()}")
    ph.dtr = True
    binary_command = command.to_binary_command_string()
    ph.write(binary_command)
    time.sleep(0.5) # We need to wait for an answer

def read_mv_result():

    ph.dtr = False
    recipent = ph.read()
    number_of_bytes : bytes = ph.read()
    command_acted_upon = ph.read()
    reply_device_id = [ph.read(), ph.read(), ph.read(), ph.read()]
    length = ord(number_of_bytes)
    data = ph.read((length - (1+4+1)))
    checksum = ph.read()
    reply_end = ph.read(2)
    reply = SerialReply(recipent, number_of_bytes, command_acted_upon, device_id, data, checksum)
    print(f"Has read mv result: {reply}")
    return reply

def read_result():
    ph.dtr = False
    result = ph.readline()
    print(f"Read result: {result}")
    ph.read()
    return result


def main():
    command = device + request_mV + device_id
    # command = device + request_rackID
    command += [get_checksum(command)]
    command.extend(line_end)
    command_string = generate_command_string(command)


    bytecommand = bytes(command_string, "charmap")

    print(bytecommand)
    send_request_mv_command("F.0.1.22")
    read_mv_result()


if __name__ == "__main__":
    main()
