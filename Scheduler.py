import math

import pandas
import pandas as pd
import datetime
from typing import *
import heapq

from PH_Meter import PH_Meter

from PumpSystem import PumpSystem
from PumpTasks import PumpTask
import yaml





class Scheduler:

    timer = datetime.datetime

    def __init__(self, scheduler_settings):
        self.settings = scheduler_settings

    def start(self, selected_protocol_path : str, ph_probe_calibration_data_path : str) -> None:
        selected_protocol = self.select_instruction_sheet(selected_protocol_path)
        with open(ph_probe_calibration_data_path, "r") as file:
            ph_probe_calibration_data = yaml.safe_load(file)

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
        print("\n\nStart running")

        # task_queue is sorted by time for next operation
        while 0 < len(task_queue):
            current_task = self.get_next_ready_task(task_queue)
            self.handle_task(current_task, ph_meter, pump_system, records, task_queue)

        return records

    def handle_task(self, current_task: PumpTask, ph_meter: PH_Meter, pump_system: PumpSystem, records: pd.DataFrame, task_queue: List[PumpTask]):
        expected_ph = current_task.get_expected_ph_at_current_time()
        measured_ph = self.measure_associated_task_ph(current_task, ph_meter)
        delay = current_task.minimum_delay
        if math.isnan(measured_ph):  # Corresponds to not getting a connection to the ph probe
            delay = 1/10  # Wait 10 seconds to try again
        elif self.should_pump(expected_ph, measured_ph):
            pump_system.pump(current_task.pump_id)
        self.record_done_step(current_task, expected_ph, measured_ph, self.should_pump(expected_ph, measured_ph), records)
        self.reschedule_task(current_task, delay, task_queue)

    def reschedule_task(self, current_task: PumpTask, delay: float, task_queue: List[PumpTask]):
        current_task.time_next_operation = self.timer.now() + datetime.timedelta(minutes=delay)
        if current_task.time_next_operation < current_task.get_end_time():
            heapq.heappush(task_queue, current_task)
        # Else the task is done.

    def record_done_step(self, current_task: PumpTask, expected_ph: float, measured_ph: float, did_pump: bool, records: pd.DataFrame):
        record = {"PumpTask": current_task.pump_id, "TimePoint": self.timer.now(), "ExpectedPH": expected_ph,
                  "ActualPH": measured_ph, "DidPump": did_pump}
        if self.settings["scheduler"]['ShouldPrintSchedulingMessages']:
            print(f"Did the following: {record}")
            print()
        records.loc[len(records.index)] = record

    def measure_associated_task_ph(self, current_task: PumpTask, ph_meter: PH_Meter):
        try:
            measured_ph = ph_meter.measure_ph_with_probe_associated_with_task(current_task)
        except:
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
        start_time = self.timer.now()
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








