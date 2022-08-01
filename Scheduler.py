import math
import os

import pandas
import pandas as pd
import datetime
from typing import *
import heapq

from PH_Meter import PH_Meter, PhReadException

from PumpSystem import PumpSystem
from PumpTasks import PumpTask
import yaml



class Scheduler:

    timer = datetime.datetime

    def __init__(self, scheduler_settings: dict) -> None:
        self.settings: dict = scheduler_settings

    def start(self, selected_protocol_path: str) -> None:
        selected_protocol = self.select_instruction_sheet(selected_protocol_path)

        ph_meter, pump_system = self.setup_ph_meter_and_pump_system(self.settings["PhCalibrationDataPath"], selected_protocol)

        results_file_path = self.create_results_file(selected_protocol_path)
        task_queue = self.initialize_task_priority_queue(selected_protocol)
        recorded_data = self.run_tasks(results_file_path, task_queue, ph_meter, pump_system)
        self.save_recorded_data(results_file_path, recorded_data)

    def setup_ph_meter_and_pump_system(self, ph_probe_calibration_data_path, selected_protocol):
        with open(ph_probe_calibration_data_path, "r") as file:
            ph_probe_calibration_data = yaml.safe_load(file)
        ph_meter = PH_Meter(self.settings["phmeter"], ph_probe_calibration_data)
        ph_meter.initialize_connection()
        pump_system = PumpSystem(selected_protocol, self.settings["pumps"])
        pump_system.initialize_connection()
        pump_system.configure_pumps()
        return ph_meter, pump_system

    def create_results_file(self, selected_protocol_path: str) -> str:
        protocol_file_name = os.path.splitext(selected_protocol_path)[0]
        results_file_name = f"{protocol_file_name}_results_{self.timer.now()}.xlsx"
        if self.settings["scheduler"]["ShouldRecordStepsWhileRunning"]:
            file = open(results_file_name, "w+")
            file.close()
        return results_file_name

    def run_tasks(self, results_file_path: str, task_queue: List[PumpTask], ph_meter: PH_Meter, pump_system: PumpSystem) -> pd.DataFrame:
        records = pd.DataFrame(columns=['PumpTask', 'TimePoint', 'ExpectedPH', 'ActualPH', 'DidPump'])
        print("\n\nStart running")
        self.handle_tasks_until_done(ph_meter, pump_system, records, results_file_path, task_queue)
        return records

    def handle_tasks_until_done(self, ph_meter, pump_system, records, results_file_path, task_queue):
        # task_queue is sorted by time for next operation
        while 0 < len(task_queue):
            current_task = self.get_next_ready_task(task_queue)
            self.handle_task(current_task, ph_meter, pump_system, records, task_queue, results_file_path)

    def handle_task(self, current_task: PumpTask, ph_meter: PH_Meter, pump_system: PumpSystem,
                    records: pd.DataFrame, task_queue: List[PumpTask], results_file_path: str):
        expected_ph = current_task.get_expected_ph_at_current_time()
        measured_ph = self.measure_associated_task_ph(current_task, ph_meter)
        delay = current_task.minimum_delay
        if math.isnan(measured_ph):  # Corresponds to not getting a connection to the ph probe
            delay = 1/10  # Wait 10 seconds to try again
        elif self.should_pump(expected_ph, measured_ph):
            pump_system.pump(current_task.pump_id)
        self.record_result_of_step(current_task, expected_ph, measured_ph, self.should_pump(expected_ph, measured_ph),
                                   records, results_file_path)
        self.reschedule_task(current_task, delay, task_queue)

    def reschedule_task(self, current_task: PumpTask, delay: float, task_queue: List[PumpTask]):
        current_task.time_next_operation = self.timer.now() + datetime.timedelta(minutes=delay)
        if current_task.time_next_operation < current_task.get_end_time():
            heapq.heappush(task_queue, current_task)
        elif current_task.next_task is not None:  # It is time to start on the next task
            self.reschedule_task(current_task.next_task, current_task.next_task.minimum_delay, task_queue)
        # Else the task is done.

    def record_result_of_step(self, current_task: PumpTask, expected_ph: float, measured_ph: float,
                              did_pump: bool, records: pd.DataFrame, results_file_path: str):
        record = {"PumpTask": current_task.pump_id, "TimePoint": self.timer.now(), "ExpectedPH": expected_ph,
                  "ActualPH": measured_ph, "DidPump": did_pump}
        if self.settings["scheduler"]['ShouldPrintSchedulingMessages']:
            print(f"Did the following: {record}")
            print()
        records.loc[len(records.index)] = record
        if self.settings["scheduler"]["ShouldRecordStepsWhileRunning"]:
            # Since it is an excel file, we can not just append the new record to the file.
            # So we just write everything
            self.save_recorded_data(results_file_path, records)

    def measure_associated_task_ph(self, current_task: PumpTask, ph_meter: PH_Meter):
        try:
            measured_ph = ph_meter.measure_ph_with_probe_associated_with_task(current_task)
        except PhReadException:
            # Sometimes, something goes wrong with measuring the ph, so we reschedule the task for 10 seconds later.
            measured_ph = float("NaN")
        return measured_ph

    def get_next_ready_task(self, task_queue: List[PumpTask]):
        current_task = heapq.heappop(task_queue)
        if self.settings["scheduler"]['ShouldPrintSchedulingMessages']:
            print(f"Task: {current_task.pump_id}, at: {self.timer.now()}")
        current_task.wait_until_time_to_execute_task()
        return current_task

    def should_pump(self, expected_ph: float, measured_ph: float):
        return not math.isnan(measured_ph) and measured_ph < expected_ph

    def initialize_task_priority_queue(self, protocol: pd.DataFrame) -> List[PumpTask]:
        task_queue = []
        start_time = self.timer.now()  # We want the same start time for all the tasks
        for index, row in protocol.iterrows():
            pump_id = row["Pump"]
            on_or_off = row["On/off"]
            ph_meter_id: (str, str) = tuple(row["pH probe"].split("_"))
            remaining_information = row.to_list()[3:]
            current_pump_task = self.get_pump_task_from_information_list(pump_id, on_or_off, ph_meter_id, start_time, remaining_information)
            heapq.heappush(task_queue, current_pump_task)
        return task_queue

    # Recursive parsing of pump tasks
    def get_pump_task_from_information_list(self, pump_id: int, on_or_off: str, ph_meter_id: (str, str),
                                            start_time: datetime, information: list) -> Optional[PumpTask]:
        if len(information) == 0 or math.isnan(information[0]):  # The information is nan if there are only some rows in the protocol with multiple tasks.
            return None
        else:
            task_time, ph_at_start, ph_at_end, dose_volume, minimum_delay = tuple(information[0:5])
            next_task = self.get_pump_task_from_information_list(pump_id, on_or_off, ph_meter_id,
                                                                 start_time + datetime.timedelta(minutes=task_time), information[5:])
            return PumpTask(pump_id=pump_id,
                            ph_meter_id=ph_meter_id,
                            task_time=task_time,
                            ph_at_start=ph_at_start,
                            ph_at_end=ph_at_end,
                            dose_volume=dose_volume,
                            minimum_delay=minimum_delay,
                            start_time=start_time,
                            time_next_operation=start_time,
                            next_task=next_task)

    def select_instruction_sheet(self, protocol_path) -> pd.DataFrame:
        return pandas.read_excel(protocol_path)

    def getMVAtSelectedProbes(self, selected_probes: List[str]) -> dict[str, float]:
        ph_meter = PH_Meter(self.settings["phmeter"], dict())
        ph_meter.initialize_connection()

        probe_to_mv_value = {}
        for probe in selected_probes:
            module_id, _ = tuple(probe.split("_"))
            module_mv_response = ph_meter.get_mv_values_of_module(module_id)
            mv_value = ph_meter.get_mv_values_of_probe(module_mv_response, probe)
            probe_to_mv_value[probe] = mv_value

        ph_meter.disconnect()  # Must be done, as we cannot establish more than one connection to the ph meter.

        return probe_to_mv_value

    def save_recorded_data(self, results_file_path: str, recorded_data: pd.DataFrame) -> None:
        recorded_data.to_excel(results_file_path, index=False)

    def restart_run(self, selected_protocol_path: str, filename_of_old_run_data: str) -> pd.DataFrame:
        selected_protocol = self.select_instruction_sheet(selected_protocol_path)
        task_queue = self.initialize_task_priority_queue(selected_protocol)
        # The tasks will have the wrong start-time. We will get the original start time from the records:
        old_records = pd.read_excel(filename_of_old_run_data)
        start_time = old_records["TimePoint"][0]
        self.offset_tasks_to_new_start_time(old_records, start_time, task_queue)
        # Then we can simply start running the tasks, and the internal logic will handle the rest.
        ph_meter, pump_system = self.setup_ph_meter_and_pump_system(self.settings["scheduler"]["PhCalibrationDataPath"], selected_protocol)
        self.handle_tasks_until_done(ph_meter, pump_system, old_records, filename_of_old_run_data, task_queue)
        return old_records

    def offset_tasks_to_new_start_time(self, old_records, start_time, tasks):
        for task in tasks:
            while task is not None:
                task.start_time = start_time
                task_records = old_records.loc[old_records['PumpTask'] == task.pump_id]
                last_time_task_was_handled = task_records["TimePoint"][task_records.index[len(task_records.index) - 1]]
                task.time_next_operation = last_time_task_was_handled + datetime.timedelta(minutes=task.minimum_delay)
