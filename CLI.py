import time
from tkinter.filedialog import askopenfilename
from typing import List, Set

import yaml

import main
from Scheduler import Scheduler


class CLI:
    selected_protocol_path = "simple_test_protocol.xlsx"
    calibration_data_path = "calibration_data.yml"

    def __init__(self, settings_path="config.yml"):

        with open(settings_path, 'r') as file:
            self.settings = yaml.safe_load(file)
        self.scheduler = Scheduler(self.settings)

    def start(self) -> None:
        print("Starting CLI")

        print("Settings can be changed in the config.yml file.")


        while True:
            self.printPossibleCommands()

            inputCommand = self.get_input()

            print()

            if inputCommand == "1":
                self.calibrate_ph_probes(self.selected_protocol_path)
            elif inputCommand == "2":
                self.selected_protocol_path = self.set_protocol_used_for_run()
            elif inputCommand == "3":
                self.scheduler.start()
                break
            elif inputCommand == "4":
                self.assign_pump_ids()
            elif inputCommand == "5":
                self.restart_failed_run()
                break
            elif inputCommand == "6":
                print("Exiting program.")
                break
            else:
                print("Viable input not given. Try again.")

            print()

    def printPossibleCommands(self) -> None:
        print("Options:")
        print("1 - Calibrate ph-measuring devices. Old calibration data will be used if this is not done.")
        print(f"2 - Set protocol used for run. Currently \"{self.selected_protocol_path}\".")
        print("3 - Run selected protocol.")
        print("4 - Assign new ID's for the pumps.")
        print("5 - Restart failed run - not implemented yet.")
        print("6 - Exit program.")
        print()
        print("Input:")

    def restart_failed_run(self) -> None:
        print("Not implemented yet.")

    def assign_pump_ids(self) -> None:
        print("Not implemented yet.")

    def set_protocol_used_for_run(self) -> None:
        selected_protocol = askopenfilename()
        print(f"Selected protocol: {selected_protocol}")
        return selected_protocol

    def calibrate_ph_probes(self, selected_protocol_path: str) -> None:
        selected_protocol = self.scheduler.select_instruction_sheet(selected_protocol_path)
        ph_probes_used_in_protocol: Set[str] = set(selected_protocol["pH probe"].to_list())

        selected_probes = self.get_probes_to_calibrate(ph_probes_used_in_protocol)

        low_pH_mv_values, low_pH = self.get_ph_calibration_values("low", selected_probes)
        high_pH_mv_values, high_ph = self.get_ph_calibration_values("high", selected_probes)

        self.record_calibration_data(high_ph, high_pH_mv_values, low_pH, low_pH_mv_values, selected_probes)

        print("Calibration finished.")

    def get_ph_calibration_values(self, ph_level: str, selected_probes: List[str]) -> (dict[str, float], float):
        print(f"Place the probes in a buffer with a {ph_level} pH. Enter the pH of this buffer:")
        ph = float(self.get_input())
        print("Wait 5 seconds for calibration.")
        time.sleep(5)
        print("Reading the mV values from the ph-meter.")
        pH_mv_values = self.scheduler.getMVAtSelectedProbes(selected_probes)
        print(f"The mV values for the different probes are: {pH_mv_values}")
        return pH_mv_values, ph

    def get_probes_to_calibrate(self, ph_probes_used_in_protocol: Set[str]) -> List[str]:
        print(f"The following probes are used in the selected protocol: {ph_probes_used_in_protocol}")
        print(f"Select the probes to be used by writing them as a comma separated list.")
        print("Write 'ALL' to select all probes used in the protocol")
        raw_selected_probes = self.get_input()
        if raw_selected_probes.lower() == "all":
            selected_probes = ph_probes_used_in_protocol
        elif raw_selected_probes.replace(" ", "") == "":  # Empty input
            print("At least one probe needs to be selected. Try again:")
            return self.get_probes_to_calibrate(ph_probes_used_in_protocol)
        else:
            selected_probes = list(raw_selected_probes.replace(" ", "").split(","))
        print(f"Selected probes: {selected_probes}")
        return selected_probes

    def get_input(self) -> str:
        return input()

    def record_calibration_data(self, high_ph: float, high_pH_mv_values: dict[str, float], low_pH: float,
                                low_pH_mv_values: dict[str, float], selected_probes: List[str]) -> None:
        # Recording the calibration values
        with open(self.calibration_data_path, 'r') as file:
            old_calibration_data = yaml.safe_load(file)
            if old_calibration_data is None:
                old_calibration_data = dict()
        for probe in selected_probes:
            old_calibration_data[probe] = {"LowPH": low_pH, "LowPHmV": low_pH_mv_values[probe],
                                           "HighPH": high_ph, "HighPHmV": high_pH_mv_values[probe]}
        with open(self.calibration_data_path, 'w') as file:
            yaml.safe_dump(old_calibration_data, file)
