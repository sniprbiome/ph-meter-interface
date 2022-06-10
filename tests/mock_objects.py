from typing import List


class MockSerialConnection:

    def __init__(self, protocol):
        self.dtr = False

        self.written_commands = []
        self.write_to_read_list = []
        self.write_to_read_count = 0

        self.read_buffer = b''

    def set_write_to_read_list(self, write_to_read_list: List):
        self.write_to_read_list = write_to_read_list

    def write(self, command):
        self.written_commands.append(command)
        write_to_read_pair = self.write_to_read_list[self.write_to_read_count]
        if write_to_read_pair[0] == command:
            self.read_buffer += (write_to_read_pair[1])
        self.write_to_read_count += 1


    def read(self, numberOfBytesToRead = 1):
        byteString = ""
        for i in range(numberOfBytesToRead):
            byteString += chr(self.read_buffer[i])
        self.read_buffer = self.read_buffer[numberOfBytesToRead:]
        bytesReply = bytes(byteString, "charmap")
        return bytesReply

    def read_all(self):
        temp_storage = self.read_buffer
        self.read_buffer = b''
        return temp_storage

