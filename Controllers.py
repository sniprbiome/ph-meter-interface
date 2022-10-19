
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

    def set_setpoint(self, new_setpoint):
        self.setpoint = new_setpoint

    def calculate_output(self, measured_value):
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
