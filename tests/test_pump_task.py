
import unittest
import datetime
import mock_objects
from Controllers import DerivativeRememberController
from PumpTasks import PumpTask


class TestPumpTask(unittest.TestCase):


    def test_WaitUntilTimeToExecuteTask(self):
        start_time = datetime.datetime.now()

        task = PumpTask( pump_id=1,
                         ph_meter_id="test",
                         task_time=1440,
                         ph_at_start=5,
                         ph_at_end=6,
                         dose_volume=5,
                         dose_multiplier_pH_difference=0.1,
                         minimum_delay=6,
                         start_time=start_time,
                         time_next_operation=start_time,
                         next_task=None,
                         controller=DerivativeRememberController(6))
        mock_timer = mock_objects.MockTimer()
        task.timer = mock_timer

        # It should not wait as start_time and time_next_operation is the same
        task.wait_until_time_to_execute_task()
        self.assertEqual([], mock_timer.sleep_list)

        wait_time = 55  # seconds
        task.time_next_operation = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
        task.wait_until_time_to_execute_task()
        self.assertEqual(1, len(mock_timer.sleep_list))
        self.assertAlmostEqual(wait_time, mock_timer.sleep_list[0], 4)


