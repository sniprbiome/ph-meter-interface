import time

import pandas as pd
import yaml

import PumpTasks
from PhMeter import PhMeter
from PumpSystem import PumpSystem


class PhysicalSystems:

    def __init__(self, settings) -> None:
        self.settings = settings

        ph_probe_calibration_data = self.get_ph_calibration_data()
        self.ph_meter = PhMeter(self.settings["phmeter"], ph_probe_calibration_data)
        self.pump_system = PumpSystem(self.settings["pumps"])

    def initialize_systems(self) -> None:
        self.ph_meter.initialize_connection()
        self.pump_system.initialize_connection()

    def initialize_pumps_used_in_protocol(self, protocol: pd.DataFrame):
        self.pump_system.setup_pumps_used_in_protocol(protocol)

# Pumping

    def get_current_pump_address(self) -> bytes:
        # Assumes the pump system has been initialized.
        self.pump_system.read_from_pumps()  # clears the connection
        self.pump_system.send_pump_command(f"*ADR")
        return self.pump_system.read_from_pumps()

    def set_and_get_address_for_current_pump(self, address: int) -> bytes:
        self.pump_system.send_pump_command(f"*ADR {address}")
        time.sleep(2)
        self.pump_system.read_from_pumps()
        self.pump_system.send_pump_command(f"*ADR")
        actual_address = self.pump_system.read_from_pumps()  # hopefully the same as the input address
        return actual_address

    def pump(self, pump_id):
        self.pump_system.pump(pump_id)

# Ph

    def get_mv_values_of_selected_probes(self, selected_probes: list[str]) -> dict[str, float]:
        try:
            return self.ph_meter.get_mv_values_of_selected_probes(selected_probes)
        except Exception as e:
            print("Error when trying to get the mv values of selected probes. "
                  "Are you sure that the ph-meter is connected and turned on?")
            raise e

    def measure_ph_with_probe_associated_with_task(self, current_task: PumpTasks) -> float:
        return self.ph_meter.measure_ph_with_probe_associated_with_task(current_task)

    def get_ph_values_of_selected_probes(self, ph_probes: list[str]) -> dict[str, float]:
        return self.ph_meter.get_ph_value_of_selected_probes(ph_probes)

    def recalibrate_ph_meter(self) -> None:
        ph_probe_calibration_data = self.get_ph_calibration_data()
        self.ph_meter.update_calibration_data(ph_probe_calibration_data)

    def get_ph_calibration_data(self) -> dict[str, dict[str, int]]:
        with open(self.settings["calibration_data_path"], "r") as file:
            ph_probe_calibration_data = yaml.safe_load(file)
        return ph_probe_calibration_data
