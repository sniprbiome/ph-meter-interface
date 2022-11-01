import math
import queue


class PIDController:
    #k_proportional = 0.01
    #k_integral = 0.01
    #k_derivative = 0.0001

    stored_integral = 0
    last_error_value = 0
    last_output_value = 0

    max_integral_term = 50
    max_output_value = 50

    def __init__(self, k_proportional, k_integral, k_derivative, setpoint):
        self.k_proportional = 50 # k_proportional
        self.k_integral = 0 #0.1 # k_integral
        self.k_derivative = 5 # k_derivative
        self.setpoint = setpoint

    def set_setpoint(self, new_setpoint) -> None:
        self.setpoint = new_setpoint

    def calculate_output(self, measured_value) -> int:
        error_value = (self.setpoint - measured_value)


        effect_modifier = 1
        if error_value < 0:
            effect_modifier = 0.2

        term_proportional = effect_modifier*self.k_proportional*error_value
        self.stored_integral += effect_modifier*error_value

        # Prevent integral windup
        if self.stored_integral > self.max_integral_term:
            self.stored_integral = self.max_integral_term
        elif self.stored_integral < 0:
            self.stored_integral = 0

        term_integral = self.k_integral*self.stored_integral

        term_derivative = effect_modifier*self.k_derivative*(self.last_error_value - error_value)
        self.last_error_value = error_value


        output_value = self.last_output_value + (term_proportional + term_integral + term_derivative)

        if self.setpoint < measured_value and self.last_output_value < output_value:
            output_value = self.last_output_value

        # Output overflow prevention
        if output_value > self.max_output_value:
            output_value = self.max_output_value
        elif output_value < -self.max_output_value:
            output_value = -self.max_output_value

        if error_value < 0:
            output_value *= 0.9

        self.last_output_value = output_value

        return output_value


class PController:
    max_output_value = 50
    last_output_value = 0

    def __init__(self, k_proportional, setpoint):
        self.k_proportional = k_proportional
        self.setpoint = setpoint

    def set_setpoint(self, new_setpoint):
        self.setpoint = new_setpoint

    def calculate_output(self, measured_value):
        error_value = (self.setpoint - measured_value)

        term_proportional = self.k_proportional*error_value
        output_value = self.last_output_value - term_proportional

        # Output overflow prevention
        if output_value > self.max_output_value:
            output_value = self.max_output_value
        elif output_value < -self.max_output_value:
            output_value = -self.max_output_value

        return output_value

class SimpleController:

    last_pump_amount = 0


    def __init__(self, k_proportional, k_integral, k_derivative, setpoint):
        self.setpoint = setpoint

    def set_setpoint(self, new_setpoint):
        self.setpoint = new_setpoint

    def calculate_output(self, measured_value):
        if measured_value < self.setpoint:
            self.last_pump_amount += 1
            return self.last_pump_amount
        else:
            self.last_pump_amount -= 1
            if self.last_pump_amount < 0:
                self.last_pump_amount = 0
            return 0

class DerivativeController:

    last_pump_amount = 0
    last_measurement = -1000000

    def __init__(self, k_proportional, k_integral, k_derivative, setpoint):
        self.setpoint = setpoint

    def set_setpoint(self, new_setpoint):
        self.setpoint = new_setpoint

    def calculate_output(self, measured_value):
        delta_measurement = measured_value - self.last_measurement
        self.last_measurement = measured_value
        if measured_value < self.setpoint:
            if delta_measurement < 0.015 or 0.2 < (self.setpoint - measured_value):
                self.last_pump_amount += 1
            elif 0 < self.last_pump_amount:
                self.last_pump_amount += 0
            return self.last_pump_amount
        else:
            self.last_pump_amount += -1
            if self.last_pump_amount < 0:
                self.last_pump_amount = 0
            return 0

class DerivativeRememberController:

    last_pump_amount = 0
    QUEUE_LENGTH = 5
    MAX_ALLOWED_DELTA = 0.01

    def __init__(self, setpoint):
        self.setpoint = setpoint
        self.measured_values = queue.Queue()

    def set_setpoint(self, new_setpoint):
        self.setpoint = new_setpoint

    def calculate_output(self, measured_value: float) -> int:
        if self.measured_values.qsize() == 0: # Initialisation. Only run once.
            for i in range(0, self.QUEUE_LENGTH):
                self.measured_values.put(measured_value)

        last_measurement = list(self.measured_values.queue)[self.QUEUE_LENGTH - 1]
        delta_measurement = measured_value - last_measurement
        self.measured_values.put(measured_value)
        self.measured_values.get()
        if measured_value < self.setpoint:
            if delta_measurement < self.MAX_ALLOWED_DELTA or 0.5 < (self.setpoint - measured_value):
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
            if (self.MAX_ALLOWED_DELTA*5 < measured_value - self.setpoint):
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


