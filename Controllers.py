import math
import queue

class DerivativeControllerWithMemory:

    last_pump_amount = 0
    QUEUE_LENGTH = 5
    MAX_ALLOWED_DELTA = 0.01

    def __init__(self):
        self.measured_values = queue.Queue()

    def calculate_output(self, setpoint, measured_value: float) -> int:
        if self.measured_values.qsize() == 0: # Initialisation. Only run once.
            for i in range(0, self.QUEUE_LENGTH):
                self.measured_values.put(measured_value)

        last_measurement = list(self.measured_values.queue)[self.QUEUE_LENGTH - 1]
        delta_measurement = measured_value - last_measurement
        self.measured_values.put(measured_value)
        self.measured_values.get()
        if measured_value < setpoint:
            if delta_measurement < self.MAX_ALLOWED_DELTA or 0.5 < (setpoint - measured_value):
                # If the increase is not very steep, we increase the amount pumped.
                # Also done if the pH difference is very big.
                if self.within_allowed_delta_over_time_period():
                    self.last_pump_amount += 1
            elif 0 < self.last_pump_amount and not self.within_allowed_delta_over_time_period():
                # If the increase is to steep we decrease it.
                self.last_pump_amount += -1
            amount_to_pump = self.last_pump_amount
        else:
            # If we are above the expected value we decrease the amount pumped.
            # We decrease it by a large amount if the measured value is a lot higher than the expected value
            if (self.MAX_ALLOWED_DELTA*5 < measured_value - setpoint):
                self.last_pump_amount = math.floor(self.last_pump_amount*0.5)
                if self.last_pump_amount < 0:
                    self.last_pump_amount = 0
            else:
                self.last_pump_amount += -1
                if self.last_pump_amount < 0:
                    self.last_pump_amount = 0

            amount_to_pump = self.last_pump_amount

        return amount_to_pump
    
    def within_allowed_delta_over_time_period(self) -> bool:
        queue_values = list(self.measured_values.queue)
        totalIncrease = (queue_values[self.QUEUE_LENGTH - 1] - queue_values[0])
        return totalIncrease < 5*self.MAX_ALLOWED_DELTA


