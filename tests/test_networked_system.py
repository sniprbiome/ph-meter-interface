import datetime
import multiprocessing
import os
import unittest
from threading import Thread
from time import sleep
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

import multiprocessing as mp
import traceback


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

    @patch("Networking.PhysicalSystemServer.PhysicalSystemServer.connect_to_devices", return_value=None)
    def start_server(self, mock):
        process = Thread(target=self.physical_system_server.begin_listening)
        process.start()
        self.physical_system_server_thread = process

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



    @patch("PumpSystem.PumpSystem.setup_pumps_used_in_protocol", return_value=None)
    def test_updates_pumps_and_probes_used(self, _):
        protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        self.create_mock_ph_solution_setup(protocol)
        process = Process(target=start_client_initialize_pumps,
                          args=tuple([self.settings, "1", protocol, "test_complete_system_single_client.xlsx"]))
        process.start()
        process.join()


        self.assertEqual(set(['F.0.1.21_1', 'F.0.1.22_1', 'F.0.1.22_2', 'F.0.1.22_3', 'F.0.1.22_4']), self.physical_system_server.used_probes)
        self.assertEqual(set([1,2,3,4,5]), self.physical_system_server.used_pumps)
        self.physical_system_server.stop()

    @patch("PumpSystem.PumpSystem.setup_pumps_used_in_protocol", return_value=None)
    def test_updates_pumps_and_probes_used_collision(self, _):
        protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        protocol2 = Scheduler.select_instruction_sheet("test_protocol_overlap.xlsx")
        self.create_mock_ph_solution_setup(protocol)
        process = Process(target=start_client_initialize_pumps,
                          args=tuple([self.settings, "1", protocol, "None"]))
        process2 = Process(target=start_client_initialize_pumps,
                          args=tuple([self.settings, "1", protocol2, "None"]))
        process.start()
        sleep(1)
        process2.start()
        process.join()
        process2.join()

        self.assertEqual(set(['F.0.1.21_1', 'F.0.1.22_1', 'F.0.1.22_2', 'F.0.1.22_3', 'F.0.1.22_4']),
                         self.physical_system_server.used_probes)
        self.assertEqual(set([1, 2, 3, 4, 5]), self.physical_system_server.used_pumps)
        self.physical_system_server.stop_server = True
        self.physical_system_server.stop()

    @patch("PumpSystem.PumpSystem.setup_pumps_used_in_protocol", return_value=None)
    def test_updates_pumps_and_probes_disconnect(self, _):
        protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        protocol2 = Scheduler.select_instruction_sheet("test_protocol_overlap.xlsx")
        self.create_mock_ph_solution_setup(protocol)
        process = Process(target=start_client_and_disconnect,
                          args=tuple([self.settings, "1", protocol, "None"]))
        process2 = Process(target=start_client_initialize_pumps,
                           args=tuple([self.settings, "1", protocol2, "None"]))
        process.start()
        process.join()
        process2.start()
        process2.join()


        self.assertEqual(set(['F.0.1.22_1', 'F.0.1.22_2']),
                         self.physical_system_server.used_probes)
        self.assertEqual(set([1, 6]), self.physical_system_server.used_pumps)
        self.physical_system_server.stop_server = True
        self.physical_system_server.stop()

    def test_complete_system_single_client(self):
        protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        self.create_mock_ph_solution_setup(protocol)
        old_task_priority_queue = list(self.scheduler.initialize_task_priority_queue(protocol))
        old_task_priority_queue.sort(key=lambda x: x.pump_id)

        process = Process(target=start_client,
                          args=tuple([self.settings, "1", protocol, "test_complete_system_single_client.xlsx"]))
        process.start()
        process.join()
        self.assertEquals(set(), self.physical_system_server.used_probes)
        self.assertEquals(set(), self.physical_system_server.used_pumps)
        self.physical_system_server.stop_server = True

        records = pd.read_excel("test_complete_system_single_client.xlsx")

        self.verify_valid_run(old_task_priority_queue, records)
        self.physical_system_server.stop()

    def test_complete_system_two_clients(self):
        protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        protocol2 = Scheduler.select_instruction_sheet("test_protocol_seperate.xlsx")
        self.create_mock_ph_solution_setup(protocol)
        self.create_mock_ph_solution_setup(protocol2)

        old_task_priority_queue1 = list(self.scheduler.initialize_task_priority_queue(protocol))
        old_task_priority_queue1.sort(key=lambda x: x.pump_id)

        old_task_priority_queue2 = list(self.scheduler.initialize_task_priority_queue(protocol2))
        old_task_priority_queue2.sort(key=lambda x: x.pump_id)

        process1 = Thread(target=start_client,
                          args=tuple([self.settings, "1", protocol, "test_complete_system_single_client.xlsx"]))

        process2 = Thread(target=start_client,
                          args=tuple([self.settings, "2", protocol2, "test_complete_system_second_client.xlsx"]))

        process1.start()
        process2.start()
        process1.join()
        process2.join()
        self.assertEquals(set(), self.physical_system_server.used_probes)
        self.assertEquals(set(), self.physical_system_server.used_pumps)

        records1 = pd.read_excel("test_complete_system_single_client.xlsx")
        records2 = pd.read_excel("test_complete_system_second_client.xlsx")

        self.verify_valid_run(old_task_priority_queue1, records1)
        print(records2)
        self.verify_valid_run(old_task_priority_queue2, records2)
        self.physical_system_server.stop()


    def verify_valid_run(self, old_task_priority_queue, records):
        print(old_task_priority_queue)
        for i in range(0, len(old_task_priority_queue)):
            current_task = old_task_priority_queue[i]
            id = old_task_priority_queue[i].pump_id
            currentPumpTaskRecords = records.loc[records['PumpTask'] == id]
            rows = [row for index, row in currentPumpTaskRecords.iterrows()]
            # The start time should be approximately the start time of the task
            # Here we assume a minute
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


def start_client_initialize_pumps(settings, client_id, protocol, save_path):
    print(f"Starting client {client_id}")
    physical_system = PhysicalSystemsClient(settings)
    physical_system.client_id = client_id
    physical_system.initialize_systems()

    physical_system.initialize_pumps_used_in_protocol(protocol)
    print(f"Finished client {client_id}")
    return physical_system


def start_client(settings, client_id, protocol, save_path):
    print(f"Starting client {client_id}")
    physical_system = PhysicalSystemsClient(settings)
    physical_system.client_id = client_id
    scheduler = Scheduler.Scheduler(settings, physical_system)
    mock_timer = mock_objects.MockTimer()
    scheduler.timer = mock_timer
    physical_system.initialize_systems()

    # Tasks
    task_priority_queue = scheduler.initialize_task_priority_queue(protocol)
    for task in task_priority_queue:
        while task is not None:
            task.timer = mock_timer
            task.datetimer = mock_timer
            task.shouldPrintWhenWaiting = False
            task = task.next_task

    scheduler.initialize_task_priority_queue(protocol)
    records = scheduler.run_tasks(save_path, task_priority_queue)
    scheduler.save_recorded_data(save_path, records)
    print(f"Finished client {client_id}")
    return physical_system


def start_client_and_disconnect(settings, client_id, protocol, save_path):
    physical_system = start_client_initialize_pumps(settings, client_id, protocol, save_path)
    physical_system.disconnect(protocol)


class Process(mp.Process):
    def __init__(self, *args, **kwargs):
        mp.Process.__init__(self, *args, **kwargs)
        self._pconn, self._cconn = mp.Pipe()
        self._exception = None

    def start(self):
        try:
            mp.Process.start(self)
            self._cconn.send(None)
        except Exception as e:
            tb = traceback.format_exc()
            self._cconn.send((e, tb))
            self._exception = e
            # raise e  # You can still rise this exception if you need to

    @property
    def exception(self):
        if self._pconn.poll():
            self._exception = self._pconn.recv()
        return self._exception