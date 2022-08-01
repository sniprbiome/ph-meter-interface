import heapq
import unittest

import yaml

import main
from PH_Meter import PH_Meter
import mock_objects
from Scheduler import Scheduler


class TestBase(unittest.TestCase):

    def setUp(self) -> None:
        with open('test_config.yml', 'r') as file:
            settings = yaml.safe_load(file)
        self.scheduler = Scheduler(settings['scheduler'])

    def test_selectInstructionSheet(self) -> None:
        protocol = self.scheduler.select_instruction_sheet("test_protocol.xlsx")
        self.assertEqual(5, len(protocol))  # Quick check that we got the correct sheet

    def test_InitializeTasks_containsCorrectTasks(self) -> None:
        protocol = self.scheduler.select_instruction_sheet("test_protocol.xlsx")
        task_priority_queue = self.scheduler.initialize_task_priority_queue(protocol)
        self.assertEqual(5, len(task_priority_queue))
        # We check all tasks have been added, here just by looking at the ph_meter_id
        module_id_list = map(lambda x: x.ph_meter_id, task_priority_queue)
        self.assertIn(("F.0.1.22", "1"), module_id_list)
        self.assertIn(("F.0.1.22", "2"), module_id_list)
        self.assertIn(("F.0.1.22", "3"), module_id_list)
        self.assertIn(("F.0.1.22", "4"), module_id_list)
        self.assertIn(("F.0.1.21", "1"), module_id_list)

    def test_canHandlerMultiOperationTasks(self) -> None:
        protocol = self.scheduler.select_instruction_sheet("test_protocol_multi_task.xlsx")
        task_priority_queue = self.scheduler.initialize_task_priority_queue(protocol)
        self.assertEqual(2, len(task_priority_queue))
        # We check all tasks have been added, here just by looking at the ph_meter_id
        task_priority_queue.sort(key=lambda x: x.ph_meter_id)

        self.assertIsNone(task_priority_queue[0].next_task)  # The task that is not a multi task

        first_task = task_priority_queue[1]
        self.assertEqual(120, first_task.task_time)
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





