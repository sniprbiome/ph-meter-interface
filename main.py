import time
from socket import timeout
import serial
from dataclasses import dataclass
from typing import *

device = [ord('M')]
device_id = [15, 1, 0, 34]
request_rackID = [2, 5]
request_mV = [6, 205]
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

@dataclass
class SerialReply:
    recipient: bytes
    lenght_of_reply: bytes
    command_acted_upon: bytes
    reply_device_id: List[str]
    data: list
    checksum: bytes



def get_checksum(command: list) -> list:
    return sum(command)

def generate_command_string(command: list) -> str:
    output = ""
    for i in command:
        output += chr(i)
    return output

def send_command(command):
    print(f"Send command: {command}")
    ph.dtr = True
    ph.write(command)
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
    #bytecommand = bytes(command_string, "charmap")
    # bytecommand = b'M\x06\n\x0f\x01\x00\x22\x8f\r\n'
    # bytecommand=b"\xFF\x4D\x06\xCD\x0F\x00\x01\x13\x43\x0D\x0A\xFF"
    # bytecommand = b'\xFFM\x06\n\x0f\x01\x00"\xc2\x8f\r\n\xFF'
    # bytecommand= b"\xFF\x4D\x06\x0A\x0F\x00\x01\x13\x80\x0D\x0A\xFF"
    # bytecommand=b"\x4D\x06\xCD\x0F\x00\x01\x13\x43\x0D\x0A"
    # bytecommand=b'\xFFM\x06\n\x0f\x01\x00"\x8f\r\n\xFF'
    # bytecommand = "\xFF\x4D\x06\x14\x0F\x00\x01\x13\x8A\x0D\x0A\xFF".encode("charmap")
    # bytecommand = "\xFF\x4D\x06\xCD\x0F\x00\x01\x13\x43\x0D\x0A\xFF".encode("charmap")

    print(int.from_bytes(b'\xcd', byteorder="big"))
    bytecommand_old = b'\x4D\x06\xCD\x0F\x00\x01\x13\x43\x0D\x0A'
    bytecommand = bytecommand_old
    #print(bytecommand)
    #print(bytecommand_old)
    #read_result()
    #read_result()
    #assert bytecommand == bytecommand_old
    send_command(bytecommand)
    read_result()
    read_result()

    send_command(bytecommand)
    read_mv_result()
    read_result()
    read_result()


if __name__ == "__main__":
    main()
