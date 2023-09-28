import math
import os
import time

import pandas
import pandas as pd
import datetime
from typing import *
import heapq

import Logger
from Controllers import DerivativeControllerWithMemory
from KeypressDetector import KeypressDetector
from Networking.PhysicalSystemsClient import PhysicalSystemsClient
from PhysicalSystems import PhysicalSystems
from PhMeter import PhReadException
from PhysicalSystemsInterface import PhysicalSystemsInterface

from PumpTasks import PumpTask


def select_instruction_sheet(protocol_path) -> pd.DataFrame:
    return pandas.read_excel(protocol_path)

class Scheduler:

    timer = datetime.datetime
    start_time = None

    def __init__(self, scheduler_settings: dict, physical_systems: PhysicalSystemsInterface) -> None:
        self.settings: dict = scheduler_settings
        self.physical_systems = physical_systems
        self.start_time = self.timer.now() 

    def start(self, selected_protocol_path: str) -> None:
        selected_protocol = select_instruction_sheet(selected_protocol_path)
        self.physical_systems.initialize_pumps_used_in_protocol(selected_protocol)
        results_file_path = self.create_results_file(selected_protocol_path)
        task_queue = self.initialize_task_priority_queue(selected_protocol)
        if (self.settings["scheduler"]["ShouldInitiallyEnsureCorrectPHBeforeStarting"]):
            self.run_ensure_correct_start_pH_value(selected_protocol, task_queue)
            task_queue = self.initialize_task_priority_queue(selected_protocol)
        self.start_time = self.timer.now()
        recorded_data = self.run_tasks(results_file_path, task_queue)
        self.save_recorded_data(results_file_path, recorded_data)
        self.physical_systems.disconnect(selected_protocol)

    def create_results_file(self, selected_protocol_path: str) -> str:
        protocol_file_name = os.path.splitext(selected_protocol_path)[0]
        timer_string: str = str(self.timer.now()).replace(":", "_")  # Windows do not allow ':' in filenames
        results_file_name = f"{protocol_file_name}_results_{timer_string}.xlsx"
        if self.settings["scheduler"]["ShouldRecordStepsWhileRunning"]:
            file = open(results_file_name, "w+")
            file.close()
        return results_file_name

    def run_tasks(self, results_file_path: str, task_queue: List[PumpTask]) -> pd.DataFrame:
        records = pd.DataFrame(columns=['PumpTask', 'TimePoint', 'ExpectedPH', 'ActualPH', 'DidPump', 'PumpMultiplier'])
        print("\n\nStart running")
        self.handle_tasks_until_done(records, results_file_path, task_queue)
        return records

    def handle_tasks_until_done(self, records: pd.DataFrame, results_file_path: str, task_queue: list[PumpTask]) -> None:

        detector = KeypressDetector()

        # task_queue is sorted by time for next operation
        while 0 < len(task_queue):
            self.pause_on_keypress(detector)
            current_task = self.get_next_ready_task(task_queue)
            self.handle_task(current_task, records, task_queue, results_file_path)

    def pause_on_keypress(self, detector):
        if detector.get_has_key_been_pressed():
            print("Pausing until enter is pressed... ")
            print()
            input()
            print("Starting again")
            print()
            detector.reset_has_key_been_pressed()

    def handle_task(self, current_task: PumpTask, records: pd.DataFrame, task_queue: List[PumpTask], results_file_path: str) -> None:
        expected_ph = current_task.get_expected_ph_at_current_time()
        measured_ph = self.measure_associated_task_ph(current_task)
        number_of_pumps = self.calculate_number_of_pumps(current_task.controller, expected_ph, measured_ph)
        delay = current_task.minimum_delay
        if math.isnan(measured_ph):  # Corresponds to not getting a connection to the ph probe
            delay = 1/10  # Wait 10 seconds to try again
        elif 0 < number_of_pumps:
            self.physical_systems.pump_n_times(current_task.pump_id, number_of_pumps)
        self.record_result_of_step(current_task, expected_ph, measured_ph, 0 < number_of_pumps,
                                   number_of_pumps, records, results_file_path)
        self.reschedule_task(current_task, delay, task_queue)



    def reschedule_task(self, current_task: PumpTask, delay: float, task_queue: List[PumpTask]) -> None:
        current_task.time_next_operation = self.timer.now() + datetime.timedelta(minutes=delay)
        if current_task.time_next_operation < current_task.get_end_time():
            heapq.heappush(task_queue, current_task)
        elif current_task.next_task is not None:  # It is time to start on the next task
            self.reschedule_task(current_task.next_task, current_task.next_task.minimum_delay, task_queue)
        # Else the task is done.

    def record_result_of_step(self, current_task: PumpTask, expected_ph: float, measured_ph: float
                              , did_pump: bool, number_of_pumps: int, records: pd.DataFrame, results_file_path: str) -> None:
        record = {"PumpTask": current_task.pump_id, "TimePoint": self.timer.now(), "ExpectedPH": expected_ph,
                  "ActualPH": measured_ph, "DidPump": did_pump, "PumpMultiplier": number_of_pumps}
        if self.settings["scheduler"]['ShouldPrintSchedulingMessages']:
            display_record = {"TimePoint": record["TimePoint"], "PumpTask": record["PumpTask"],
                              "ExpectedPH": round(record["ExpectedPH"], 2), "ActualPH": round(record["ActualPH"], 2),
                              "DidPump": record["DidPump"]}
            print(f"Did the following: {display_record}")
            print()
        records.loc[len(records.index)] = record
        if self.settings["scheduler"]["ShouldRecordStepsWhileRunning"]:
            # Since it is an excel file, we can not just append the new record to the file.
            # So we just write everything
            self.save_recorded_data(results_file_path, records)

    def measure_associated_task_ph(self, current_task: PumpTask) -> float:
        try:
            measured_ph = self.physical_systems.measure_ph_with_probe_associated_with_task(current_task)
        except Exception as e:  # PhReadException originally, but this does not work when the server is used.
            # Sometimes, something goes wrong with measuring the ph, so we reschedule the task for 10 seconds later.
            Logger.standardLogger.log(e)
            measured_ph = float("NaN")
        return measured_ph

    def get_next_ready_task(self, task_queue: List[PumpTask]) -> PumpTask:
        current_task = heapq.heappop(task_queue)
        if self.settings["scheduler"]['ShouldPrintSchedulingMessages']:
            print(f"Task: {current_task.pump_id}, at: {self.timer.now()}")
        current_task.wait_until_time_to_execute_task()
        return current_task

    def should_pump(self, expected_ph: float, measured_ph: float) -> bool:
        return not math.isnan(measured_ph) and measured_ph < expected_ph

    def initialize_task_priority_queue(self, protocol: pd.DataFrame) -> List[PumpTask]:
        task_queue = []
        start_time = self.timer.now()  # We want the same start time for all the tasks
        for index, row in protocol.iterrows():
            pump_id = row["Pump"]
            on_or_off = row["On/off"]
            if on_or_off == 0:
                continue
            ph_meter_id: (str, str) = tuple(row["pH probe"].split("_"))
            remaining_information = row.to_list()[3:]
            current_pump_task = self.get_pump_task_from_information_list(pump_id, on_or_off, ph_meter_id,
                                                                         start_time, remaining_information)
            heapq.heappush(task_queue, current_pump_task)
        return task_queue

    # Recursive parsing of pump tasks
    def get_pump_task_from_information_list(self, pump_id: int, on_or_off: str, ph_meter_id: (str, str),
                                            start_time: datetime, information: list) -> Optional[PumpTask]:
        # The information is nan if there are only some rows in the protocol with multiple tasks.
        if len(information) == 0 or math.isnan(information[0]):
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
                            next_task=next_task,
                            controller=DerivativeControllerWithMemory())

    def save_recorded_data(self, results_file_path: str, recorded_data: pd.DataFrame) -> None:
        recorded_data.to_excel(results_file_path, index=False)

    def restart_run(self, selected_protocol_path: str, filename_of_old_run_data: str) -> pd.DataFrame:
        selected_protocol = select_instruction_sheet(selected_protocol_path)
        task_queue = self.initialize_task_priority_queue(selected_protocol)
        # The tasks will have the wrong start-time. We will get the original start time from the records:
        old_records = pd.read_excel(filename_of_old_run_data)
        start_time = old_records["TimePoint"][0]
        self.offset_tasks_to_new_start_time(old_records, start_time, task_queue)
        # Then we can simply start running the tasks, and the internal logic will handle the rest.
        self.handle_tasks_until_done(old_records, filename_of_old_run_data, task_queue)
        return old_records

    def offset_tasks_to_new_start_time(self, old_records: pd.DataFrame, start_time: datetime, tasks: list[PumpTask]):
        for task in tasks:
            task.start_time = start_time
            task_records = old_records.loc[old_records['PumpTask'] == task.pump_id]
            last_time_task_was_handled = task_records["TimePoint"][task_records.index[len(task_records.index) - 1]]
            task.time_next_operation = last_time_task_was_handled + datetime.timedelta(minutes=task.minimum_delay)

    def run_ensure_correct_start_pH_value(self, protocol: pd.DataFrame, task_queue: list[PumpTask]) -> None:
        wait_time_in_minutes = 1.0
        any_ph_below_start_ph_value = True
        dose_multiplication_factor = self.settings["scheduler"]["IncreasedPumpFactorWhenPerformingInitialCorrection"]
        # Will continue running until all pumptasks have a pH above the ph_at_start value.
        print("The program will now ensure that the pH values of all the solutions are above the target start values.")
        print("It will continue pumping every minute until this is the case.")

        target_ph_values = dict()
        for task in task_queue:
            target_ph_values[task.pump_id] = task.ph_at_start

        while any_ph_below_start_ph_value:
            any_ph_below_start_ph_value = False
            measured_ph_values = dict()
            for current_task in task_queue:
                measured_ph = self.measure_associated_task_ph(current_task)
                measured_ph_values[current_task.pump_id] = round(measured_ph, 2)
                if self.should_pump(current_task.ph_at_start, measured_ph):
                    any_ph_below_start_ph_value = True
                    for i in range(math.floor(dose_multiplication_factor)):
                        self.physical_systems.pump(current_task.pump_id)
            print(f"Measured pH: {measured_ph_values}")
            print(f"Target pH:   {target_ph_values}")
            print()
            time.sleep(wait_time_in_minutes*60)

        print("All pH's are now above the desired starting values.")

        # Removing the multiplication factor
        #PhysicalSystems.set_pump_dose_multiplication_factor(protocol, 1)

    def calculate_number_of_pumps(self, controller: DerivativeControllerWithMemory, expected_ph: float, measured_ph: float):
        if self.adaptive_pumping_currently_enabled():
            return controller.calculate_output(expected_ph, measured_ph)
        else:
            return 1 if measured_ph < expected_ph else 0

    def adaptive_pumping_currently_enabled(self) -> bool:
        adaptive_start_time = self.settings["scheduler"]["AdaptivePumpingActivateAfterNHours"]
        return adaptive_start_time <= 0 or self.start_time + datetime.timedelta(hours=adaptive_start_time) < self.timer.now()


