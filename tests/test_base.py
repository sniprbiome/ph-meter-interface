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
        module_id_list = list(map(lambda x: x.ph_meter_id, task_priority_queue))
        self.assertIn(("F.0.1.22", "1"), module_id_list)
        self.assertIn(("F.0.1.22", "2"), module_id_list)
        self.assertIn(("F.0.1.22", "3"), module_id_list)
        self.assertIn(("F.0.1.22", "4"), module_id_list)
        self.assertIn(("F.0.1.21", "1"), module_id_list)

        # There are extra pump tasks for the two first tasks, but not the next tasks after that
        self.assertIsNotNone(task_priority_queue[0].next_task)
        self.assertIsNotNone(task_priority_queue[1].next_task)
        self.assertIsNone(task_priority_queue[2].next_task)
        self.assertIsNone(task_priority_queue[3].next_task)
        self.assertIsNone(task_priority_queue[4].next_task)

        self.assertIsNone(task_priority_queue[0].next_task.next_task)
        self.assertIsNone(task_priority_queue[1].next_task.next_task)




