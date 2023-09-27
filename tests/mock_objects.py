import datetime
import math
from typing import List, Tuple


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

    time_dependent_actions = []

    def __init__(self) -> None:
        self.sleep_list = []
        self.current_time = datetime.datetime.now()

    def sleep(self, seconds: float) -> None:
        self.sleep_list.append(seconds)
        self.current_time += datetime.timedelta(seconds=seconds)
        for action in self.time_dependent_actions:
            action(self.current_time)

    def now(self) -> datetime.datetime:
        return self.current_time

    def set_time(self, new_time: datetime.datetime) -> None:
        self.current_time = new_time

    def add_time_dependent_action(self, action) -> None:
        self.time_dependent_actions.append(action)


class MockPhSolution:

    sensitivity = 1

    def __init__(self, initialMV):
        self.moduleMvs = initialMV

    def addVolumeOfBaseToSolution(self, volume: float, module: str, target: int) -> None:
        self.moduleMvs[module][target - 1] -= volume*self.sensitivity

    def addVolumeOfAcidToSolution(self, volume: float, module: str, target: int) -> None:
        self.addVolumeOfBaseToSolution(-volume, module, target)

    def setSensitivity(self, new_sensitivity):
        self.sensitivity = new_sensitivity

    def getMVsOfModule(self, module: str) -> List[int]:
        return self.moduleMvs[module]

    def getPhCommandOfSolution(self, module: str) -> bytes:

        mvs = self.getMVsOfModule(module)

        mvsBytes = b''
        for mv in mvs:
            # 0.1 mv per integer.
            if mv < 0: # It uses two's complement
                mv = 65536 - abs(mv)
            int_mv = int(mv)
            mvBytes = int_mv.to_bytes(2, 'big')
            mvsBytes += mvBytes


        binaryReply =  b'P\x0E\x10\x0f\x00\x01' + bytes(chr(int(module.split(".")[3], 16)), "charmap") + mvsBytes +  b'\x00' + b'\x0D\x0A'

        return binaryReply


class Counter:
    count = 0

    def increment(self):
        self.count += 1

    def read_count(self):
        return self.count

    def reset(self):
        self.count = 0

class MockAcidProducingBacteria:

    def __init__(self, intervals: List[Tuple[datetime.datetime, float]]):
        self.intervals = intervals
        self.current_time = self.intervals[0][0]

    def add_acid_according_to_time(self, new_time):

        for i in range(0, len(self.intervals) - 1):
            if (self.intervals[i][0] <= new_time and new_time <= self.intervals[i+1][0]):
                current_interval_index = i
                break

        # linear progress between the two acid factors
        time_factor = ((new_time - self.intervals[current_interval_index][0]))/(self.intervals[current_interval_index+1][0] - self.intervals[current_interval_index][0])
        current_acid_production_factor = time_factor*(self.intervals[current_interval_index+1][1] - self.intervals[current_interval_index][1]) + self.intervals[current_interval_index][1]

        time_difference = new_time - self.current_time
        self.current_time = new_time
        acid_produced = (time_difference.seconds/60)*current_acid_production_factor
        return acid_produced


class MockEmailServer:

    has_logged_in = False

    emails_received = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __init__(self, sender_email, sender_smtp_server, sender_email_password, sender_ssl_port, receiver_email):
        self.sender_email = sender_email
        self.sender_smtp_server = sender_smtp_server
        self.sender_email_password = sender_email_password
        self.sender_ssl_port = sender_ssl_port
        self.receiver_email = receiver_email

    def login(self, sender_email, password):
        if self.sender_email != sender_email or self.sender_email_password != password:
            raise Exception("Wrong login information")
        self.has_logged_in = True

    def sendmail(self, sender_email, receiver_email_list, raw_email):
        receiver_email = receiver_email_list[0]
        if not self.has_logged_in or self.sender_email != sender_email or self.receiver_email != receiver_email:
            raise Exception("Wrong send email information")

        self.emails_received.append((sender_email, receiver_email, raw_email))


