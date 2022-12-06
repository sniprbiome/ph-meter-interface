import datetime
import os
import unittest
from unittest.mock import patch, MagicMock

import pandas as pd
import matplotlib.pyplot as plt
import yaml

import Controllers
import main
from PhMeter import PhMeter
import mock_objects
from PhysicalSystems import PhysicalSystems
from PumpSystem import PumpSystem
from PumpTasks import PumpTask
import matplotlib.pyplot as plt

import Scheduler


class Test_complete_system(unittest.TestCase):

    def setUp(self):
        self.mock_timer = mock_objects.MockTimer()
        with open('test_config.yml', 'r') as file:
            self.settings = yaml.safe_load(file)

        with open('test_calibration_data.yml', 'r') as file:
            self.calibration_data = yaml.safe_load(file)

        self.physical_system = PhysicalSystems(self.settings)
        self.scheduler = Scheduler.Scheduler(self.settings, self.physical_system)
        self.protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        self.scheduler.timer = self.mock_timer

        # ph-meter:
        self.ph_meter = PhMeter(self.settings['phmeter'], self.calibration_data)
        self.physical_system.ph_meter = self.ph_meter
        self.mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.ph_meter.serial_connection = self.mock_serial_connection
        self.ph_meter.timer = self.mock_timer
        self.physical_system.ph_meter = self.ph_meter

        # Pumps
        self.pump_system = PumpSystem(self.settings["pumps"])
        self.physical_system.pump_system = self.pump_system
        self.mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.pump_system.serial_connection = self.mock_serial_connection
        self.pump_system.timer = self.mock_timer
        self.physical_system.pump_system = self.pump_system

        # Tasks
        self.task_priority_queue = self.scheduler.initialize_task_priority_queue(self.protocol)
        for task in self.task_priority_queue:
            while task is not None:
                task.timer = self.mock_timer
                task.datetimer = self.mock_timer
                task.shouldPrintWhenWaiting = False
                task = task.next_task

        # PhSolutions

    def create_mock_ph_solution_setup(self):
        self.mock_ph_solution = mock_objects.MockPhSolution(
            {"F.0.1.22": [800, 800, 800, 800], "F.0.1.21": [800, 10000, 10000, 10000]})

        self.ph_meter.serial_connection.add_write_action(b'M\x06\n\x0f\x00\x01"\x8f\r\n',
                                                         lambda: self.mock_ph_solution.getPhCommandOfSolution(
                                                             "F.0.1.22"))

        self.ph_meter.serial_connection.add_write_action(b'M\x06\n\x0f\x00\x01!\x8e\r\n',
                                                         lambda: self.mock_ph_solution.getPhCommandOfSolution(
                                                             "F.0.1.21"))

        pump_associated_volumes = self.pump_system.get_pump_associated_dispention_volume(self.protocol)
        self.pump_system.serial_connection.add_write_action(b'1 RUN\r',
                                                            lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(
                                                                int(pump_associated_volumes[(1)]), "F.0.1.22", 1))
        self.pump_system.serial_connection.add_write_action(b'2 RUN\r',
                                                            lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(
                                                                int(pump_associated_volumes[(2)]), "F.0.1.22", 2))
        self.pump_system.serial_connection.add_write_action(b'3 RUN\r',
                                                            lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(
                                                                int(pump_associated_volumes[(3)]), "F.0.1.22", 3))
        self.pump_system.serial_connection.add_write_action(b'4 RUN\r',
                                                            lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(
                                                                int(pump_associated_volumes[(4)]), "F.0.1.22", 4))
        self.pump_system.serial_connection.add_write_action(b'5 RUN\r',
                                                            lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(
                                                                int(pump_associated_volumes[(5)]), "F.0.1.21", 1))

    def test_complete_system(self):
        self.create_mock_ph_solution_setup()
        old_task_priority_queue = list(self.task_priority_queue)
        old_task_priority_queue.sort(key=lambda x: x.pump_id)
        records = self.scheduler.run_tasks("None", self.task_priority_queue)


        for pumpTask in [1, 2, 3, 4, 5]:

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

                # it should pump when expected pH is less than actual pH
                # Not true with the new controllers
                #self.assertEqual(currentRow["DidPump"], currentRow["ActualPH"] < currentRow["ExpectedPH"])

                # The actual pH should not vary by a lot compared to the expected ph. Here we say 0.2
                self.assertLess(abs(currentRow["ActualPH"] - currentRow["ExpectedPH"]), 0.2)

                # currentPumpTaskRecords.plot(x="TimePoint", y="ActualPH", kind="line")
                # plt.show()

        # self.scheduler.save_recorded_data("testrun.xlsx", records)

    def test_multi_task_changes_task(self):
        print("TODO")
        self.protocol = Scheduler.select_instruction_sheet("test_protocol_multi_task.xlsx")

        self.task_priority_queue = self.scheduler.initialize_task_priority_queue(self.protocol)
        for task in self.task_priority_queue:
            while task is not None:
                task.timer = self.mock_timer
                task.datetimer = self.mock_timer
                task.shouldPrintWhenWaiting = False
                task = task.next_task

        self.create_mock_ph_solution_setup()
        old_task_priority_queue = list(self.task_priority_queue)
        self.assertEqual(2, len(old_task_priority_queue))
        old_task_priority_queue.sort(key=lambda x: x.pump_id)
        records = self.scheduler.run_tasks("None", self.task_priority_queue)
        task = old_task_priority_queue[0]
        total_task_time = lambda t: t.task_time + total_task_time(t.next_task) if t is not None else 0
        expected_total_task_time = total_task_time(task)
        actual_total_task_time = (records.iloc[len(records.index) - 1]["TimePoint"] - records.iloc[0]["TimePoint"])
        self.assertAlmostEqual(expected_total_task_time, actual_total_task_time.seconds/60, -1)


    def test_modelDipInPH(self):

        ##### Setup

        self.protocol = Scheduler.select_instruction_sheet("test_protocol_sudden_dip.xlsx")

        self.task_priority_queue = self.scheduler.initialize_task_priority_queue(self.protocol)
        for task in self.task_priority_queue:
            while task is not None:
                task.timer = self.mock_timer
                task.datetimer = self.mock_timer
                task.shouldPrintWhenWaiting = False
                task = task.next_task

        self.mock_ph_solution = mock_objects.MockPhSolution(
            {"F.0.1.22": [900, 800, 800, 800]})
        self.mock_ph_solution.setSensitivity(4)

        self.ph_meter.serial_connection.add_write_action(b'M\x06\n\x0f\x00\x01"\x8f\r\n',
                    lambda: self.mock_ph_solution.getPhCommandOfSolution("F.0.1.22"))

        pump_associated_volumes = self.pump_system.get_pump_associated_dispention_volume(self.protocol)
        #pump_associated_volumes[1] = 1
        self.pump_system.serial_connection.add_write_action(b'1 RUN\r',
                                                            lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(
                                                                int(pump_associated_volumes[(1)]), "F.0.1.22", 1))

        bacteria = mock_objects.MockAcidProducingBacteria([(self.mock_timer.now(), 1.2),
                                                           (self.mock_timer.now() + datetime.timedelta(hours=5), 1.8),
                                                           (self.mock_timer.now() + datetime.timedelta(hours=7), 10),
                                                           (self.mock_timer.now() + datetime.timedelta(hours=11), 3.2),
                                                           (self.mock_timer.now() + datetime.timedelta(hours=25), 1.2)])
        self.mock_timer.add_time_dependent_action(lambda time: self.mock_ph_solution.addVolumeOfAcidToSolution(bacteria.add_acid_according_to_time(time),  "F.0.1.22", 1))


        old_task_priority_queue = list(self.task_priority_queue)
        old_task_priority_queue.sort(key=lambda x: x.pump_id)
        records = self.scheduler.run_tasks("None", self.task_priority_queue)
        print(records["TimePoint"].tolist())

        plt.plot(records["TimePoint"].tolist(), (records["PumpMultiplier"]/20 + records["ExpectedPH"]).tolist(), label="Pumped")
        plt.plot(records["TimePoint"].tolist(), records["ActualPH"].tolist(), label="Actual")
        plt.plot(records["TimePoint"].tolist(), records["ExpectedPH"].tolist(), label="Expected")
        print("kage")

    def test_adaptive_pumping_disabled_at_start(self):
        self.settings["scheduler"]["AdaptivePumpingActivateAfterNHours"] = 1.2
        self.scheduler.start_time = self.mock_timer.now()
        self.assertFalse(self.scheduler.adaptive_pumping_currently_enabled())
        self.assertEqual(self.scheduler.calculate_number_of_pumps(Controllers.DerivativeControllerWithMemory(), 7.0, -10.0), 1)

        self.mock_timer.sleep(60*60)
        self.assertFalse(self.scheduler.adaptive_pumping_currently_enabled())

        self.mock_timer.sleep(60*30) # Now we surpass the wait time.
        self.assertTrue(self.scheduler.adaptive_pumping_currently_enabled())
        self.assertEqual(self.scheduler.calculate_number_of_pumps(Controllers.DerivativeControllerWithMemory(), 7.0, -10.0), 1)
        self.assertEqual(self.scheduler.calculate_number_of_pumps(Controllers.DerivativeControllerWithMemory(), 7.0, 8.0), 0)
        
    def test_dipInPHRecovery(self):

        ##### Setup

        self.protocol = Scheduler.select_instruction_sheet("test_protocol_sudden_dip.xlsx")

        self.task_priority_queue = self.scheduler.initialize_task_priority_queue(self.protocol)
        for task in self.task_priority_queue:
            while task is not None:
                task.timer = self.mock_timer
                task.datetimer = self.mock_timer
                task.shouldPrintWhenWaiting = False
                task = task.next_task

        self.mock_ph_solution = mock_objects.MockPhSolution(
            {"F.0.1.22": [1100, 800, 800, 800]})
        self.mock_ph_solution.setSensitivity(4)

        self.ph_meter.serial_connection.add_write_action(b'M\x06\n\x0f\x00\x01"\x8f\r\n',
                    lambda: self.mock_ph_solution.getPhCommandOfSolution("F.0.1.22"))

        pump_associated_volumes = self.pump_system.get_pump_associated_dispention_volume(self.protocol)
        #pump_associated_volumes[1] = 1
        self.pump_system.serial_connection.add_write_action(b'1 RUN\r',
                                                            lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(
                                                                int(pump_associated_volumes[(1)]), "F.0.1.22", 1))

        bacteria = mock_objects.MockAcidProducingBacteria([(self.mock_timer.now(), 1),
                                                           (self.mock_timer.now() + datetime.timedelta(hours=25), 20.2)])
        self.mock_timer.add_time_dependent_action(lambda time: self.mock_ph_solution.addVolumeOfAcidToSolution(bacteria.add_acid_according_to_time(time),  "F.0.1.22", 1))


        old_task_priority_queue = list(self.task_priority_queue)
        old_task_priority_queue.sort(key=lambda x: x.pump_id)
        records = self.scheduler.run_tasks("None", self.task_priority_queue)
        #print(records["TimePoint"].tolist())

        plt.plot(records["TimePoint"].tolist(), (records["PumpMultiplier"]/20 + records["ExpectedPH"]).tolist(), label="Pumped")
        plt.plot(records["TimePoint"].tolist(), records["ActualPH"].tolist(), label="Actual")
        plt.plot(records["TimePoint"].tolist(), records["ExpectedPH"].tolist(), label="Expected")
        print("kage")

    def test_handleSuddenDipInPH(self):
        # Sometimes bacteria become more active for a period of time.
        # We want to ensure it can handle it without to big a dip in pH using the multipump.

        self.create_mock_ph_solution_setup()
        start_time = self.mock_timer.now()
        pump_associated_volumes = self.pump_system.get_pump_associated_dispention_volume(self.protocol)

        # Add a certain amount of acid at specific timepoints.
        def measurePHAndCorrectAtTimepoint():
            min_time = start_time + datetime.timedelta(hours=1)
            current_time = self.mock_timer.now()
            max_time = start_time + datetime.timedelta(hours=1.5)
            if (min_time <= current_time <= max_time):
                # Corresponds to the bacteria producing extra acid.
                self.mock_ph_solution.addVolumeOfAcidToSolution(3 * int(pump_associated_volumes[(2)]), "F.0.1.22", 2)
            else:
                pass
            return self.mock_ph_solution.getPhCommandOfSolution("F.0.1.22")

        self.ph_meter.serial_connection.write_actions[b'M\x06\n\x0f\x00\x01"\x8f\r\n'] = \
            (lambda: measurePHAndCorrectAtTimepoint())

        self.task_priority_queue = [self.task_priority_queue[1]]  # Only interested in the second task
        old_task_priority_queue = list(self.task_priority_queue)
        old_task_priority_queue.sort(key=lambda x: x.pump_id)
        records = self.scheduler.run_tasks("None", self.task_priority_queue)

        rows = [row for index, row in records.iterrows()]


        for i in range(len(rows) - 1):
            currentRow = rows[i]
            nextRow = rows[i + 1]

            # The pH should not get to low, as it should then pump multiple times.
            # Here we say 0.3
            self.assertLess(abs(currentRow["ActualPH"] - currentRow["ExpectedPH"]), 0.3)



    def test_records_data_every_step(self):
        self.settings["scheduler"]["ShouldRecordStepsWhileRunning"] = True
        testfilename = "testrun.xlsx"
        results_file_path = self.scheduler.create_results_file(testfilename)
        if os.path.exists(results_file_path):
            os.remove(results_file_path)
        self.create_mock_ph_solution_setup()
        testTask = PumpTask(1, ("F.0.1.22", "1"), 1000, 0, 100, 1000, 0.5, 10, datetime.datetime.now(),
                            datetime.datetime.now(), None, Controllers.DerivativeControllerWithMemory())
        records = pd.DataFrame(columns=['PumpTask', 'TimePoint', 'ExpectedPH', 'ActualPH', 'DidPump', 'PumpMultiplier'])
        self.scheduler.handle_task(testTask, records, [], results_file_path)
        self.assertEqual(1, len(records.index))

        savedRecords = pd.read_excel(results_file_path)
        os.remove(results_file_path)
        self.assertEqual(1, len(savedRecords.index))
        self.assertCountEqual(records["PumpTask"], savedRecords["PumpTask"])
        self.assertAlmostEqual(records["ExpectedPH"][0], savedRecords["ExpectedPH"][0], delta=0.000001)
        self.assertCountEqual(records["ActualPH"], savedRecords["ActualPH"])
        self.assertCountEqual(records["DidPump"], savedRecords["DidPump"])
        self.assertAlmostEqual(records["TimePoint"][0], savedRecords["TimePoint"][0],
                               delta=datetime.timedelta(seconds=0.01))
        self.assertCountEqual(records["PumpMultiplier"], savedRecords["PumpMultiplier"])

    @patch("Scheduler.Scheduler.initialize_task_priority_queue")
    def test_restart_half_finished_run(self, mock2: MagicMock):
        oldTaskQueue = list(self.task_priority_queue)
        mock2.return_value = oldTaskQueue
        self.create_mock_ph_solution_setup()

        # We change the tasks to only run halfway to simulate a stop
        prior_next_task = {}
        for task in oldTaskQueue:
            task.task_time = task.task_time // 2
            task.next_task = None  # We temporarily remove multitasks, so it only runs halfway trough the first part of the task.
            prior_next_task[task.pump_id] = task.next_task
            task.ph_at_end = (task.ph_at_end + task.ph_at_start) / 2

        records = self.scheduler.run_tasks("testrun.xlsx", self.task_priority_queue)
        oldRecords = pd.DataFrame(records)
        self.scheduler.save_recorded_data("testrun_stopped.xlsx", records)

        # We restart it 20 minutes later
        number_of_rows = len(records.index)
        timepoint = records["TimePoint"][number_of_rows - 1]
        # I think we need to substract two hours because of timezones
        timepoint_stopped = datetime.datetime.fromtimestamp((timepoint.timestamp())) - datetime.timedelta(hours=2)
        self.mock_timer.set_time(timepoint_stopped)
        self.mock_timer.sleep(60 * 20)

        for task in oldTaskQueue:
            task.task_time = task.task_time * 2
            task.next_task = prior_next_task[task.pump_id]
            task.ph_at_end = (task.ph_at_end - task.ph_at_start) * 2 + task.ph_at_start
        oldTaskQueueBackup = list(oldTaskQueue)
        print("Restarting run")
        new_records = self.scheduler.restart_run(self.settings["protocol_path"], "testrun_stopped.xlsx")
        # self.scheduler.save_recorded_data("testrun_stopped_started.xlsx", new_records)

        # The last task in old tasks should have the same ph in the next task in new tasks,
        # iff no pumping was done
        for task in oldTaskQueueBackup:
            oldTaskRecords = oldRecords.loc[oldRecords["PumpTask"] == task.pump_id]
            index = oldTaskRecords.index[len(oldTaskRecords.index) - 1]
            lastOldRecordForTask = oldTaskRecords.loc[index]

            newTaskRecords = new_records.loc[new_records["PumpTask"] == task.pump_id]
            newIndex = newTaskRecords.index[len(oldTaskRecords.index)]
            firstNewRecordForTask = newTaskRecords.loc[newIndex]

            if lastOldRecordForTask["DidPump"]:
                self.assertLess(lastOldRecordForTask["ActualPH"], firstNewRecordForTask["ActualPH"])
            else:
                self.assertEqual(lastOldRecordForTask["ActualPH"], firstNewRecordForTask["ActualPH"])

            # The expected ph should be higher:

            precise_time_difference: float = (firstNewRecordForTask["TimePoint"] - lastOldRecordForTask[
                "TimePoint"]).total_seconds() / 60
            fractionTimeDifference = precise_time_difference / task.task_time
            expected_ph_difference = fractionTimeDifference * (task.ph_at_end - task.ph_at_start)

            self.assertAlmostEqual(lastOldRecordForTask["ExpectedPH"] + expected_ph_difference,
                                   firstNewRecordForTask["ExpectedPH"], delta=0.001)

            # The start time should be the same for almost all tasks
            self.assertTrue(abs((task.start_time - new_records.loc[0]["TimePoint"]).total_seconds() / 60) < 1)

            # Super ugly but it gets the work done
            get_total_time = lambda t: t.task_time + get_total_time(t.next_task) if t is not None else 0
            get_last_task = lambda t: t.next_task if t.next_task is not None else t

            expected_total_time = get_total_time(task)
            last_task = get_last_task(task)

            expected_end_time = task.start_time + datetime.timedelta(minutes=expected_total_time)
            actual_end_time = newTaskRecords.iloc[len(newTaskRecords.index) - 1]["TimePoint"]
            self.assertTrue(abs(expected_end_time - actual_end_time).total_seconds() / 60 < last_task.minimum_delay)

    @patch("time.sleep", return_value=None)
    def test_runEnsureCorrectStartPHValue(self, _):
        self.create_mock_ph_solution_setup()
        self.mock_ph_solution.moduleMvs = {"F.0.1.22": [1000, 1000, 900, 700], "F.0.1.21": [1200, 10000, 10000, 10000]}
        old_task_priority_queue = list(self.task_priority_queue)
        old_task_priority_queue.sort(key=lambda x: x.pump_id)
        self.scheduler.run_ensure_correct_start_pH_value(self.protocol, self.task_priority_queue)

        finalMvValues = self.mock_ph_solution.moduleMvs["F.0.1.22"] + [self.mock_ph_solution.moduleMvs["F.0.1.21"][0]]

        for mVValue in finalMvValues:
            # Around the start value of pH 5.6
            self.assertLessEqual(mVValue, 800)
            self.assertGreaterEqual(mVValue, 700)

        # Check that the dose volume multiplication factor
