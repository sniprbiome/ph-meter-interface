import datetime
import multiprocessing
import os
import unittest
from threading import Thread
from typing import Callable
from unittest.mock import patch, MagicMock

import pandas as pd
import matplotlib.pyplot as plt
import yaml

from Networking.PhysicalSystemServer import PhysicalSystemServer
from Networking.PhysicalSystemsClient import PhysicalSystemsClient
from PhMeter import PhMeter
import mock_objects
from PhysicalSystems import PhysicalSystems
from PumpSystem import PumpSystem
from PumpTasks import PumpTask

import Scheduler


class Test_networked_system(unittest.TestCase):

    def setUp(self):
        self.mock_timer = mock_objects.MockTimer()
        with open('test_config.yml', 'r') as file:
            self.settings = yaml.safe_load(file)

        with open('test_calibration_data.yml', 'r') as file:
            self.calibration_data = yaml.safe_load(file)

        self.physical_system_server = PhysicalSystemServer(self.settings)
        self.start_server()
        self.real_physical_system = PhysicalSystems(self.settings)
        self.physical_system_server.physical_system = self.real_physical_system
        self.scheduler = Scheduler.Scheduler(self.settings, None)

        # ph-meter:
        self.ph_meter = PhMeter(self.settings['phmeter'], self.calibration_data)
        self.real_physical_system.ph_meter = self.ph_meter
        self.mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.ph_meter.serial_connection = self.mock_serial_connection
        self.ph_meter.timer = self.mock_timer

        # Pumps
        self.pump_system = PumpSystem(self.settings["pumps"])
        self.real_physical_system.pump_system = self.pump_system
        self.mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.pump_system.serial_connection = self.mock_serial_connection
        self.pump_system.timer = self.mock_timer

        # PhSolutions


        self.mock_ph_solution = mock_objects.MockPhSolution(
            {"F.0.1.22": [800, 800, 800, 800], "F.0.1.21": [800, 800, 800, 800]})
        self.ph_meter.serial_connection.add_write_action(b'M\x06\n\x0f\x00\x01"\x8f\r\n',
                                                         lambda: self.mock_ph_solution.getPhCommandOfSolution(
                                                             "F.0.1.22"))

        self.ph_meter.serial_connection.add_write_action(b'M\x06\n\x0f\x00\x01!\x8e\r\n',
                                                         lambda: self.mock_ph_solution.getPhCommandOfSolution(
                                                             "F.0.1.21"))

    def start_server(self):
        process = Thread(target=self.physical_system_server.begin_listening)
        process.start()

    def create_mock_ph_solution_setup(self, protocol):

        pump_associated_volumes = self.pump_system.get_pump_associated_dispention_volume(protocol)

        for index, row in protocol.iterrows():
            pump_id: int = (row['Pump'])
            command = str(pump_id).encode() + b' RUN\r'
            probe = row['pH probe'].split("_")
            module = probe[0]
            module_probe = probe[1]
            volume = int(pump_associated_volumes[pump_id])
            # Done in a weird way, as otherwise the lambdas would all turn in to the same lambda
            def action(volume=volume, module=module, module_probe=module_probe):
                return self.mock_ph_solution.addVolumeOfBaseToSolution(volume, module, int(module_probe))
            self.pump_system.serial_connection.add_write_action(command, action)

    def start_client(self, id, instructions_path, save_path):
        self.physical_system = PhysicalSystemsClient(self.settings)
        self.scheduler = Scheduler.Scheduler(self.settings, self.physical_system)
        self.protocol = Scheduler.select_instruction_sheet(instructions_path)
        self.scheduler.timer = self.mock_timer
        self.physical_system.initialize_systems()

        # Tasks
        self.task_priority_queue = self.scheduler.initialize_task_priority_queue(self.protocol)
        for task in self.task_priority_queue:
            while task is not None:
                task.timer = self.mock_timer
                task.datetimer = self.mock_timer
                task.shouldPrintWhenWaiting = False
                task = task.next_task

        records = self.scheduler.run_tasks(save_path, self.task_priority_queue)
        self.scheduler.save_recorded_data(save_path, records)

    def test_complete_system_single_client(self):
        protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        self.create_mock_ph_solution_setup(protocol)
        old_task_priority_queue = list(self.scheduler.initialize_task_priority_queue(protocol))
        old_task_priority_queue.sort(key=lambda x: x.pump_id)

        process = Thread(target=self.start_client,
                         args=tuple(["test_protocol.xlsx", "test_complete_system_single_client.xlsx"]))
        process.start()
        process.join()

        records = pd.read_excel("test_complete_system_single_client.xlsx")

        self.verify_valid_run(old_task_priority_queue, records)

    def test_complete_system_two_clients(self):
        protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        protocol2 = Scheduler.select_instruction_sheet("test_protocol_seperate.xlsx")
        self.create_mock_ph_solution_setup(protocol)
        self.create_mock_ph_solution_setup(protocol2)

        old_task_priority_queue1 = list(self.scheduler.initialize_task_priority_queue(protocol))
        old_task_priority_queue1.sort(key=lambda x: x.pump_id)

        old_task_priority_queue2 = list(self.scheduler.initialize_task_priority_queue(protocol2))
        old_task_priority_queue2.sort(key=lambda x: x.pump_id)

        process1 = Thread(target=self.start_client,
                         args=tuple(["1", "test_protocol.xlsx", "test_complete_system_single_client.xlsx"]))

        process2 = Thread(target=self.start_client,
                         args=tuple(["2", "test_protocol_seperate.xlsx", "test_complete_system_second_client.xlsx"]))

        process1.start()
        process2.start()
        process1.join()
        process2.join()

        records1 = pd.read_excel("test_complete_system_single_client.xlsx")
        records2 = pd.read_excel("test_complete_system_second_client.xlsx")

        self.verify_valid_run(old_task_priority_queue1, records1)
        self.verify_valid_run(old_task_priority_queue2, records2)

    def verify_valid_run(self, old_task_priority_queue, records):
        for pumpTask in range(1, len(old_task_priority_queue) + 1):

            currentPumpTaskRecords = records.loc[records['PumpTask'] == pumpTask]
            rows = [row for index, row in currentPumpTaskRecords.iterrows()]
            # The start time should be approximately the start time of the task
            # Here we assume a minute
            current_task = old_task_priority_queue[pumpTask - 1]
            self.assertTrue(abs((current_task.start_time - rows[0]["TimePoint"]).total_seconds() / 60) < 1)

            # The same goes for the end time:
            last_task = current_task
            while last_task.next_task is not None:
                last_task = last_task.next_task
            expected_end_time = last_task.get_end_time()
            actual_end_time = rows[len(rows) - 1]["TimePoint"]
            self.assertTrue(abs(expected_end_time - actual_end_time).total_seconds() / 60 <= last_task.minimum_delay,
                            f"{abs(expected_end_time - actual_end_time).total_seconds() / 60} compared to {last_task.minimum_delay}")

            for i in range(len(rows) - 1):
                currentRow = rows[i]
                nextRow = rows[i + 1]
                # expected pH should be strictly increasing:
                self.assertLess(currentRow["ExpectedPH"], nextRow["ExpectedPH"])
                # actual ph should be weakly increasing
                self.assertLessEqual(currentRow["ActualPH"], nextRow["ActualPH"])
                # Timepoint should be strictly increasing
                self.assertLess(currentRow["TimePoint"], nextRow["TimePoint"])

                # pH should increase exactly when it pumped the time before:
                if currentRow['DidPump']:
                    self.assertLess(currentRow["ActualPH"], nextRow["ActualPH"])
                else:
                    self.assertEqual(currentRow["ActualPH"], nextRow["ActualPH"])

                self.assertLess(abs(currentRow["ActualPH"] - currentRow["ExpectedPH"]), 0.2)
