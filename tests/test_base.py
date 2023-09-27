import datetime
import math
import unittest
from unittest.mock import patch

import pandas as pd
import yaml

from Controllers import DerivativeControllerWithMemory
from PhysicalSystems import PhysicalSystems
import Scheduler
import mock_objects
from PumpTasks import PumpTask


class TestBase(unittest.TestCase):

    def setUp(self) -> None:
        with open('test_config.yml', 'r') as file:
            settings = yaml.safe_load(file)
        self.physical_systems = PhysicalSystems(settings)
        self.pump_system = self.physical_systems.pump_system
        self.scheduler = Scheduler.Scheduler(settings, self.physical_systems)
        self.mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.pump_system.serial_connection = self.mock_serial_connection

    def test_selectInstructionSheet(self) -> None:
        protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        self.assertEqual(5, len(protocol))  # Quick check that we got the correct sheet

    def test_initializeTasks_containsCorrectTasks(self) -> None:
        protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        task_priority_queue = self.scheduler.initialize_task_priority_queue(protocol)
        self.assertEqual(5, len(task_priority_queue))
        # We check all tasks have been added, here just by looking at the ph_meter_id
        module_id_list = map(lambda x: x.ph_meter_id, task_priority_queue)
        self.assertIn(("F.0.1.22", "1"), module_id_list)
        self.assertIn(("F.0.1.22", "2"), module_id_list)
        self.assertIn(("F.0.1.22", "3"), module_id_list)
        self.assertIn(("F.0.1.22", "4"), module_id_list)
        self.assertIn(("F.0.1.21", "1"), module_id_list)

    def test_initializeTasks_ignoresOffTasks(self) -> None:
        protocol = Scheduler.select_instruction_sheet("test_protocol_off.xlsx")
        self.assertEqual(2, len(protocol))
        task_priority_queue = self.scheduler.initialize_task_priority_queue(protocol)
        self.assertEqual(1, len(task_priority_queue))

        module_id_list = list(map(lambda x: x.ph_meter_id, task_priority_queue))
        self.assertEqual(("F.0.1.22", "2"), module_id_list[0])


    def test_canHandleMultiOperationTasks(self) -> None:
        protocol = Scheduler.select_instruction_sheet("test_protocol_multi_task.xlsx")
        task_priority_queue = self.scheduler.initialize_task_priority_queue(protocol)
        self.assertEqual(2, len(task_priority_queue))
        # We check all tasks have been added, here just by looking at the ph_meter_id
        task_priority_queue.sort(key=lambda x: x.pump_id)

        self.assertIsNone(task_priority_queue[1].next_task)  # The task that is not a multi task

        first_task = task_priority_queue[0]
        self.assertEqual(240, first_task.task_time)
        self.assertAlmostEqual(5.6, first_task.ph_at_start, 4)
        self.assertAlmostEqual(6.8, first_task.ph_at_end, 4)
        self.assertEqual(10, first_task.dose_volume)
        self.assertEqual(2, first_task.minimum_delay)
        self.assertIsNotNone(first_task.next_task)

        second_task = first_task.next_task
        self.assertEqual(90, second_task.task_time)
        self.assertAlmostEqual(6.8, second_task.ph_at_start, 4)
        self.assertAlmostEqual(9, second_task.ph_at_end, 4)
        self.assertEqual(15, second_task.dose_volume)
        self.assertEqual(2, second_task.minimum_delay)
        self.assertIsNotNone(second_task.next_task)

        third_task = second_task.next_task
        self.assertEqual(80, third_task.task_time)
        self.assertAlmostEqual(9.5, third_task.ph_at_start, 4)
        self.assertAlmostEqual(11, third_task.ph_at_end, 4)
        self.assertEqual(20, third_task.dose_volume)
        self.assertEqual(3, third_task.minimum_delay)
        self.assertIsNone(third_task.next_task)

    @patch("time.sleep", return_value=None)
    def test_measureAssociatedTaskPH_noCrashWithBlankResponse(self, _):
        # It should not crash even if there is no data to fetch
        mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.physical_systems.ph_meter.serial_connection = mock_serial_connection
        start_time = datetime.datetime.now()
        task = PumpTask(pump_id=1,
                        ph_meter_id=("F.0.1.22", "1"),
                        task_time=1440,
                        ph_at_start=5,
                        ph_at_end=6,
                        dose_volume=5,
                        minimum_delay=6,
                        start_time=start_time,
                        time_next_operation=start_time,
                        next_task=None,
                        controller=DerivativeControllerWithMemory())
        blank_command = (b'M\x06\n\x0f\x00\x01"\x8f\r\n', b'')
        mock_serial_connection.set_write_to_read_list([blank_command]*10)
        self.assertTrue(math.isnan(self.scheduler.measure_associated_task_ph(task)))
        self.assertTrue(math.isnan(self.scheduler.measure_associated_task_ph(task)))
        self.assertTrue(math.isnan(self.scheduler.measure_associated_task_ph(task)))


    @patch("time.sleep", return_value=None)
    def test_measureAssociatedTaskPH_noCrashWithHalfResponse(self, _):
        # It should not crash even if there is no data to fetch
        mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.physical_systems.ph_meter.serial_connection = mock_serial_connection
        start_time = datetime.datetime.now()
        task = PumpTask(pump_id=1,
                        ph_meter_id=("F.0.1.22", "1"),
                        task_time=1440,
                        ph_at_start=5,
                        ph_at_end=6,
                        dose_volume=5,
                        minimum_delay=6,
                        start_time=start_time,
                        time_next_operation=start_time,
                        next_task=None,
                        controller=DerivativeControllerWithMemory())
        blank_command = (b'M\x06\n\x0f\x00\x01"\x8f\r\n', b'M\x03\x15\x00')
        mock_serial_connection.set_write_to_read_list([blank_command]*10)
        self.assertTrue(math.isnan(self.scheduler.measure_associated_task_ph(task)))
        self.assertTrue(math.isnan(self.scheduler.measure_associated_task_ph(task)))
        self.assertTrue(math.isnan(self.scheduler.measure_associated_task_ph(task)))

        b'P\x0E\x10\x0f\x01\x00"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0D\x0A'


    @patch("time.sleep", return_value=None)
    def test_measureAssociatedTaskPH_noCrashWithShortResponse(self, _):
        # Even if it gives a valid response that is somehow to short, it should not crash
        mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.physical_systems.ph_meter.serial_connection = mock_serial_connection
        start_time = datetime.datetime.now()
        task = PumpTask(pump_id=1,
                        ph_meter_id=("F.0.1.22", "1"),
                        task_time=1440,
                        ph_at_start=5,
                        ph_at_end=6,
                        dose_volume=5,
                        minimum_delay=6,
                        start_time=start_time,
                        time_next_operation=start_time,
                        next_task=None,
                        controller=DerivativeControllerWithMemory())

        # We give 12 bytes instead of the usual 14.
        command = (b'M\x06\n\x0f\x00\x01"\x8f\r\n', b'P\x0C\x10\x0f\x00\x01"\x00\x00\x00\x00\x00\x00\x00\x0D\x0A')
        mock_serial_connection.set_write_to_read_list([command])
        self.assertTrue(math.isnan(self.scheduler.measure_associated_task_ph(task)))

