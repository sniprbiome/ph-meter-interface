
from dataclasses import dataclass
from typing import *
import functools



LINE_END = [13, 10]


class SerialCommand:
    recipient: str
    length_of_command: int
    command: int
    device_id: str
    information_bytes: List[int]
    checksum: int

    def __init__(self, recipient: str, length_of_command: int, command: int, device_id: str, information_bytes: List[int]):
        self.recipient = recipient
        self.length_of_command = length_of_command
        self.command = command
        self.device_id = device_id
        self.information_bytes = information_bytes
        self.checksum = self.generate_checksum()

    def generate_checksum(self) -> bytes:
        return sum([ord(self.recipient), self.length_of_command, self.command] + self.device_id_string_to_hex_ID() + self.information_bytes)

    def to_binary_command_string(self):
        command_list = []
        command_list.append(ord(self.recipient))
        command_list.append(self.length_of_command)
        command_list.append(self.command)
        command_list.extend(self.device_id_string_to_hex_ID())
        command_list.extend(self.information_bytes)
        command_list.append(self.checksum)
        command_list.extend(LINE_END)

        command_string = functools.reduce(lambda a, b: a + chr(b), command_list, "")
        command_binary_string = bytes(command_string, "charmap")

        return command_binary_string

    def device_id_string_to_hex_ID(self):
        device_id_split = self.device_id.split(".")
        device_id_hex = list(map(lambda x: int(x, 16), device_id_split))
        return device_id_hex

@dataclass
class SerialReply:
    recipient: bytes
    lenght_of_reply: bytes
    command_acted_upon: bytes
    reply_device_id: List[str]
    data: list
    checksum: bytes