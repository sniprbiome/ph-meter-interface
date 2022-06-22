import heapq
import unittest

import main
from PH_Meter import PH_Meter
import mock_objects



class TestBase(unittest.TestCase):


    def test_selectInstructionSheet(self):
        protocol = main.select_instruction_sheet("../test_protocol.xlsx")
        self.assertEqual(5, len(protocol))  # Quick check that we got the correct sheet

    def test_InitializeTasks_containsCorrectTasks(self):
        protocol = main.select_instruction_sheet("../test_protocol.xlsx")
        task_priority_queue = main.initialize_task_priority_queue(protocol)
        self.assertEqual(5, len(task_priority_queue))
        # We check all tasks have been added, here just by looking at the ph_meter_id
        module_id_list = map(lambda x: x.ph_meter_id, task_priority_queue)
        self.assertIn(("F.0.1.22", "1"), module_id_list)
        self.assertIn(("F.0.1.22", "2"), module_id_list)
        self.assertIn(("F.0.1.22", "3"), module_id_list)
        self.assertIn(("F.0.1.22", "4"), module_id_list)
        self.assertIn(("F.0.1.21", "1"), module_id_list)



