import time
from socket import timeout

import pandas
import openpyxl
import serial
from dataclasses import dataclass
import datetime
from typing import *
from queue import PriorityQueue
import heapq
from heapdict import heapdict

from SerialCommands import SerialCommand, SerialReply


module_ids = ["F.0.1.13", "F.0.1.21", "F.0.1.22"]

ph = None
"""
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
"""


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


def test_ph_connection():
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


@dataclass
class PumpTask:
    pump_id: int
    ph_meter_id: (str, str)
    task_time: int  # minutes
    ph_at_start: float
    ph_at_end: float
    dose_volume: float  # ml
    minimum_delay: float  # minimum delay between dosations. In minutes.
    start_time: datetime.datetime
    time_next_operation: datetime.datetime

    # So that it can be put into a priority queue.
    def __lt__(self, nxt):
        return self.time_next_operation < nxt.time_next_operation

    def wait_until_time_to_execute_task(self):
        current_time = datetime.datetime.now()
        time_difference_in_seconds = (self.time_next_operation - current_time).total_seconds()
        if 0 < time_difference_in_seconds:
            print(f"Waiting {time_difference_in_seconds} seconds until task is ready.")
            time.sleep(time_difference_in_seconds)

    def get_expected_ph_at_current_time(self):
        current_time = datetime.datetime.now()
        total_ph_interval = self.ph_at_end - self.ph_at_start
        fraction_of_time_done = (current_time - self.start_time).total_seconds()/(self.task_time*60)
        return self.ph_at_start + total_ph_interval*fraction_of_time_done

    def get_end_time(self):
        return self.start_time + datetime.timedelta(minutes=self.task_time)

def main():

    protocol = select_intrustrion_sheet()
    # ph_connection = connect_to_ph_meter()
    # pump_connection = connect_to_pumps()
    # calibrate_ph_probes(ph_connection)
    # configure_pumps(pump_connection, protocol)
    task_queue = initialize_task_priority_queue(protocol)
    recorded_data = run_tasks(task_queue)
    # save_recorded_data(recorded_data)

def run_tasks(task_queue : List[PumpTask]):

    # task_queue is sorted by time for next operation
    while 0 < len(task_queue):
        current_task : PumpTask = heapq.heappop(task_queue)
        current_task.wait_until_time_to_execute_task()
        expected_ph = current_task.get_expected_ph_at_current_time()

        # measure_ph
        measured_ph = 5.6

        if measured_ph < expected_ph:
            print("Pump!")

        current_task.time_next_operation = datetime.datetime.now() + datetime.timedelta(minutes=current_task.minimum_delay)
        if current_task.time_next_operation < current_task.get_end_time():
            heapq.heappush(task_queue, current_task)
        # Else the task is done.


    print("Done running tasks")




def initialize_task_priority_queue(protocol):
    task_queue = []
    start_time = datetime.datetime.now()
    for index, row in protocol.iterrows():
        current_pump_task = PumpTask(pump_id=row["Pump"],
                                     ph_meter_id=tuple(row["pH probe"].split("_")),
                                     task_time=row["Step"],
                                     ph_at_start=row["pH start"],
                                     ph_at_end=row["pH end"],
                                     dose_volume=row["Dose vol."],
                                     minimum_delay=row["Force delay"],
                                     start_time=start_time,
                                     time_next_operation=start_time)

        heapq.heappush(task_queue, current_pump_task)
    return task_queue


def select_intrustrion_sheet():
    protocol_path = "Minigut.setup_FD.xlsx"
    protocol = pandas.read_excel(protocol_path)
    return protocol


if __name__ == "__main__":
    main()
