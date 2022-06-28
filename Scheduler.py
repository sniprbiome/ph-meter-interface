import math

import pandas
import pandas as pd
import datetime
from typing import *
import heapq

from pandas import Series

from PH_Meter import PH_Meter

from PumpSystem import PumpSystem
from PumpTasks import PumpTask
import yaml





class Scheduler:

    timer = datetime.datetime

    def __init__(self, scheduler_settings):
        self.settings = scheduler_settings

    def start(self, selected_protocol_path: str, ph_probe_calibration_data_path : str) -> None:
        selected_protocol = self.select_instruction_sheet(selected_protocol_path)
        with open(ph_probe_calibration_data_path, "r") as file:
            ph_probe_calibration_data = yaml.safe_load(ph_probe_calibration_data_path)

        ph_meter = PH_Meter(self.settings["phmeter"], ph_probe_calibration_data)
        ph_meter.initialize_connection()

        pump_system = PumpSystem(selected_protocol, self.settings["pumps"])
        pump_system.initialize_connection()
        pump_system.configure_pumps()

        task_queue = self.initialize_task_priority_queue(selected_protocol)
        recorded_data = self.run_tasks(task_queue, ph_meter, pump_system)
        self.save_recorded_data(recorded_data)

    def run_tasks(self, task_queue: List[PumpTask], ph_meter: PH_Meter, pump_system: PumpSystem) -> pd.DataFrame:

        records = pd.DataFrame(columns=['PumpTask', 'TimePoint', 'ExpectedPH', 'ActualPH', 'DidPump'])

        print("\n\n\nStart running")
        # task_queue is sorted by time for next operation
        while 0 < len(task_queue):
            current_task: PumpTask = heapq.heappop(task_queue)
            if self.settings["scheduler"]['ShouldPrintSchedulingMessages']:
                print(f"Task: {current_task.pump_id}, at: {self.timer.now()}")
            current_task.wait_until_time_to_execute_task()
            expected_ph = current_task.get_expected_ph_at_current_time()

            # measure_ph
            measured_ph = ph_meter.measure_ph_with_probe_associated_with_task(current_task)

            if measured_ph < expected_ph:
                pump_system.pump(current_task.pump_id)

            record = {"PumpTask": current_task.pump_id, "TimePoint": self.timer.now(), "ExpectedPH": expected_ph,
                      "ActualPH": measured_ph, "DidPump": measured_ph < expected_ph}
            if self.settings["scheduler"]['ShouldPrintSchedulingMessages']:
                print(f"Did the following: {record}")
                print()
            records.loc[len(records.index)] = record
            current_task.time_next_operation = self.timer.now() + datetime.timedelta(minutes=current_task.minimum_delay)
            if current_task.time_next_operation < current_task.get_end_time():
                heapq.heappush(task_queue, current_task)
            elif current_task.next_task is not None:
                heapq.heappush(task_queue, current_task.next_task)
            # Else the task is done.

        return records

    def initialize_task_priority_queue(self, protocol: pd.DataFrame) -> List[PumpTask]:
        task_queue = []
        start_time = self.timer.now()
        for index, row in protocol.iterrows():
            current_pump_task = self.create_pump_task_from_row(list(row), start_time)
            heapq.heappush(task_queue, current_pump_task)
        return task_queue

    def create_pump_task_from_row(self, row: list, start_time: datetime.datetime) -> PumpTask:
        if 8 < len(row) and not math.isnan(row[8]):
            next_start_time = start_time + datetime.timedelta(minutes=row[3])
            next_task = self.create_pump_task_from_row(row[0:3] + row[8:], next_start_time)
        else:
            next_task = None
        current_pump_task = PumpTask(pump_id=row[0],
                                     ph_meter_id=tuple(row[2].split("_")),
                                     task_time=row[3],
                                     ph_at_start=row[4],
                                     ph_at_end=row[5],
                                     dose_volume=row[6],
                                     minimum_delay=row[7],
                                     start_time=start_time,
                                     time_next_operation=start_time,
                                     next_task=next_task)

        return current_pump_task

    def select_instruction_sheet(self, protocol_path) -> pd.DataFrame:
        return pandas.read_excel(protocol_path)

    def getMVAtSelectedProbes(self, selected_probes: List[str]) -> dict[str, float]:
        ph_meter = PH_Meter(self.settings["phmeter"], None)
        ph_meter.initialize_connection()

        probe_to_mv_value = {}
        for probe in selected_probes:
            module_id, _ = tuple(probe.split("_"))
            module_mv_response = ph_meter.get_mv_values_of_module(module_id)
            mv_value = ph_meter.get_mv_values_of_probe(module_mv_response, probe)
            probe_to_mv_value[probe] = mv_value

        ph_meter.disconnect()  # Must be done, as we cannot establish more than one connection to the ph meter.

        return probe_to_mv_value

    def save_recorded_data(self, recorded_data: pd.DataFrame) -> None:
        recorded_data.to_excel("results.xlsx", index=False)








