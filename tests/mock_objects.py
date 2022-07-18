import datetime
import math
from typing import List


class MockSerialConnection:

    def __init__(self, protocol):
        self.dtr = False

        self.written_commands = []
        self.write_to_read_list = []
        self.write_to_read_count = 0

        self.write_actions = {}

        self.read_buffer = b''

    def set_write_to_read_list(self, write_to_read_list: List):
        self.write_to_read_list = write_to_read_list

    def add_write_action(self, command, action):
        self.write_actions[command] = action

    def write(self, command):
        self.written_commands.append(command)
        if command in self.write_actions:
            reply = self.write_actions[command]()  # Do action
            if reply is not None:
                self.read_buffer += reply
        else:
            if self.write_to_read_count == len(self.write_to_read_list):
                raise Exception(f"Error, fewer commands are in the write-to-read-list than given, "
                                f"at command {command}, list {self.write_to_read_list}, and write count {self.write_to_read_count}")
            write_to_read_pair = self.write_to_read_list[self.write_to_read_count]
            if write_to_read_pair[0] == command:
                self.read_buffer += (write_to_read_pair[1])
            else:
                raise Exception(f"Wrong write to read pair: {write_to_read_pair} and command {command}")
            self.write_to_read_count += 1
        pass


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

    def close(self):
        pass

class MockTimer:
    # mocks time and datetime.datetime

    def __init__(self) -> None:
        self.sleep_list = []
        self.current_time = datetime.datetime.now()

    def sleep(self, seconds: float) -> None:
        self.sleep_list.append(seconds)
        self.current_time += datetime.timedelta(seconds=seconds)

    def now(self) -> datetime.datetime:
        return self.current_time

    def set_time(self, new_time: datetime.datetime) -> None:
        self.current_time = new_time


class MockPhSolution:

    def __init__(self, initialMV):
        self.moduleMvs = initialMV

    def addVolumeOfBaseToSolution(self, volume: int, module: str, target: int) -> None:
        self.moduleMvs[module][target - 1] -= volume

    def getMVsOfModule(self, module: str) -> List[int]:
        return self.moduleMvs[module]

    def getPhCommandOfSolution(self, module: str) -> bytes:

        mvs = self.getMVsOfModule(module)

        mvsBytes = b''
        for mv in mvs:
            # 0.1 mv per integer.
            if mv < 0: # It uses two's complement
                mv = 65536 - abs(mv)
            mvBytes = mv.to_bytes(2, 'big')
            mvsBytes += mvBytes


        binaryReply =  b'P\x0E\x10\x0f\x00\x01' + bytes(chr(int(module.split(".")[3], 16)), "charmap") + mvsBytes +  b'\x00' + b'\x0D\x0A'

        return binaryReply


