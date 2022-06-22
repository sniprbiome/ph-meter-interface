import time
from socket import timeout

import pandas
import openpyxl
import pandas as pd
import serial
from dataclasses import dataclass
import datetime
from typing import *
from queue import PriorityQueue
import heapq
from PH_Meter import PH_Meter
from heapdict import heapdict

from PumpSystem import PumpSystem
from PumpTasks import PumpTask
from SerialCommands import PhSerialCommand, SerialReply
import yaml


module_ids = ["F.0.1.13", "F.0.1.21", "F.0.1.22"]

timer = datetime.datetime

def main():

    print("Starting")
    with open('config.yml', 'r') as file:
        settings = yaml.safe_load(file)
    protocol = select_instruction_sheet("simple_test_protocol.xlsx")
    ph_meter = PH_Meter(protocol)
    ph_meter.initialize_connection()

    pump_system = PumpSystem(protocol, settings["pumps"])
    pump_system.initialize_connection()
    pump_system.configure_pumps()

    # calibrate_ph_probes(ph_connection)
    # configure_pumps(pump_connection, protocol)
    task_queue = initialize_task_priority_queue(protocol)
    recorded_data = run_tasks(task_queue, ph_meter, pump_system)
    # save_recorded_data(recorded_data)

def run_tasks(task_queue : List[PumpTask], ph_meter: PH_Meter, pump_system: PumpSystem):

    records = pd.DataFrame(columns=['PumpTask', 'TimePoint', 'ExpectedPH', 'ActualPH', 'DidPump'])

    print("\n\n\nStart running")
    # task_queue is sorted by time for next operation
    while 0 < len(task_queue):
        current_task: PumpTask = heapq.heappop(task_queue)
        print(f"Task: {current_task.pump_id}, at: {timer.now()}")
        current_task.wait_until_time_to_execute_task()
        expected_ph = current_task.get_expected_ph_at_current_time()

        # measure_ph
        measured_ph = ph_meter.measure_ph_with_probe_associated_with_task(current_task)

        if measured_ph < expected_ph:
            pump_system.pump(current_task.pump_id)

        record = {"PumpTask": current_task.pump_id, "TimePoint": timer.now(), "ExpectedPH": expected_ph, "ActualPH": measured_ph, "DidPump": measured_ph < expected_ph}
        print(f"Did the following: {record}")
        records.loc[len(records.index)] = record
        current_task.time_next_operation = timer.now() + datetime.timedelta(minutes=current_task.minimum_delay)
        if current_task.time_next_operation < current_task.get_end_time():
            heapq.heappush(task_queue, current_task)
        # Else the task is done.

        print()

    return records


def initialize_task_priority_queue(protocol) -> List[PumpTask]:
    task_queue = []
    start_time = timer.now()
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


def select_instruction_sheet(protocol_path="Minigut.setup_FD.xlsx"):
   return pandas.read_excel(protocol_path)


if __name__ == "__main__":
    main()
