import datetime
import time
from dataclasses import dataclass


@dataclass
class PumpTask:
    pump_id: int
    ph_meter_id: (str, str)
    task_time: int  # minutes
    ph_at_start: float
    ph_at_end: float
    dose_volume: float  # ml
    minimum_delay: float  # minimum delay between dosations. In minutes.
    start_time: datetime.datetime
    time_next_operation: datetime.datetime

    # So that it can be put into a priority queue.
    def __lt__(self, nxt):
        return self.time_next_operation < nxt.time_next_operation

    def wait_until_time_to_execute_task(self):
        current_time = datetime.datetime.now()
        time_difference_in_seconds = (self.time_next_operation - current_time).total_seconds()
        if 0 < time_difference_in_seconds:
            print(f"Waiting {time_difference_in_seconds} seconds until task is ready.")
            time.sleep(time_difference_in_seconds)

    def get_expected_ph_at_current_time(self):
        current_time = datetime.datetime.now()
        total_ph_interval = self.ph_at_end - self.ph_at_start
        fraction_of_time_done = (current_time - self.start_time).total_seconds()/(self.task_time*60)
        return self.ph_at_start + total_ph_interval*fraction_of_time_done

    def get_end_time(self):
        return self.start_time + datetime.timedelta(minutes=self.task_time)
