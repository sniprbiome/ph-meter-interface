import os
import time
from tkinter.filedialog import askopenfilename
from typing import List

import pandas as pd
import yaml

from PumpSystem import PumpSystem
from Scheduler import Scheduler


class CLI:

    def __init__(self, settings_path="config.yml"):
        self.settings = self.load_settings(settings_path)
        self.scheduler = Scheduler(self.settings)

    def start(self):

        print("Starting CLI")
        print("Settings can be changed in the config.yml file.")

        while True:
            self.printPossibleCommands()

            inputCommand = self.get_input()

            print()

            if inputCommand == "1":
                self.settings["protocol_path"] = self.set_protocol_used_for_run()
            elif inputCommand == "2":
                self.calibrate_ph_probes(self.settings["protocol_path"])
                # TODO save settings.
            elif inputCommand == "3":
                self.scheduler.start(self.settings["protocol_path"])
                break
            elif inputCommand == "4":
                self.assign_pump_ids(self.settings)
            elif inputCommand == "5":
                self.restart_failed_run(self.settings["protocol_path"])
            elif inputCommand == "6":
                self.live_read_ph(self.settings["protocol_path"])
            elif inputCommand == "7":
                print("Exiting program.")
                break
            else:
                print("Viable input not given. Try again.")

            print()

    def printPossibleCommands(self):
        print("Options:")
        print(f"1 - Set protocol used for run. Currently \"{self.settings['protocol_path']}\".")
        print("2 - Calibrate ph-measuring probes. Old calibration data will be used if this is not done.")
        print("3 - Run selected protocol.")
        print("4 - Assign new ID's for the pumps.")
        print("5 - Restart failed run.")
        print("6 - Live read pH. pH will be measured using all probes in the selected protocol.")
        print("7 - Exit program.")
        print()
        print("Input:")

    def restart_failed_run(self, protocol_path: str):
        print("Enter the name of the saved run data, or write ”stop” to go back:")
        filename = self.get_input()
        if filename == "stop":
            return
        elif not os.path.exists(filename):
            print(f"The file: {filename} did not exist. Try again.")
            self.restart_failed_run(protocol_path)
        print(f"The run ”{filename}” will be restarted based on the protocol: {protocol_path}")

        self.scheduler.restart_run(protocol_path, filename)

    def assign_pump_ids(self, settings: dict) -> None:
        # Use fake protocols
        pump_system = PumpSystem(pd.DataFrame(data={"Pump": []}), settings["pumps"])
        pump_system.initialize_connection()
        print("Plug the main cable from the computer into the pump you want to assign an ID.")
        print("Then write the ID you want to assign the pump. Must be from 1 to 99.")
        print("Write STOP when you want to stop assigning ID's")
        while True:
            print("Input: ")
            input_code = self.get_input()
            if input_code.lower() == "stop":
                break
            elif input_code.lower() == "measure":
                pump_system.read_from_pumps()
                pump_system.send_pump_command(f"*ADR")
                print(f"Current pump has address: {pump_system.read_from_pumps()}")
            else:
                pump_system.send_pump_command(f"*ADR {input_code}")
                time.sleep(2)
                pump_system.read_from_pumps()
                pump_system.send_pump_command(f"*ADR")
                print(f"It now has the address: {pump_system.read_from_pumps()}")
        print("Stopped assigning ID's.")

    def set_protocol_used_for_run(self) -> str:
        selected_protocol = askopenfilename()
        print(f"Selected protocol: {selected_protocol}")
        return selected_protocol

    def calibrate_ph_probes(self, selected_protocol_path: str) -> None:
        self.scheduler.setup_ph_meter()
        ph_probes_used_in_protocol = self.get_probes_used_in_protocol(selected_protocol_path)

        selected_probes = self.choose_probes(ph_probes_used_in_protocol)

        low_pH_mv_values, low_pH = self.get_ph_calibration_values("low", selected_probes)
        high_pH_mv_values, high_ph = self.get_ph_calibration_values("high", selected_probes)

        self.record_calibration_data(high_ph, high_pH_mv_values, low_pH, low_pH_mv_values, selected_probes)

        print("Calibration finished.")

    def get_probes_used_in_protocol(self, selected_protocol_path: str) -> list[str]:
        selected_protocol = self.scheduler.select_instruction_sheet(selected_protocol_path)
        ph_probes_used_in_protocol: list[str] = list(set(selected_protocol["pH probe"].to_list()))
        ph_probes_used_in_protocol.sort()
        return ph_probes_used_in_protocol

    def get_ph_calibration_values(self, ph_level: str, selected_probes: List[str]) -> (dict[str, float], float):
        print(f"Place the probes in a buffer with a {ph_level} pH. Enter the pH of this buffer:")
        ph = self.get_input()
        wait_time = 30
        print(f"Wait {wait_time} seconds for calibration.")
        time.sleep(wait_time)
        print("Reading the mV values from the ph-meter.")
        pH_mv_values = self.scheduler.getMVAtSelectedProbes(selected_probes)
        print(f"The mV values for the different probes are: {pH_mv_values}")
        return pH_mv_values, float(ph)

    def choose_probes(self, ph_probes_used_in_protocol):
        print(f"The following probes are used in the selected protocol: {ph_probes_used_in_protocol}")
        print(f"Select the probes to be used by writing them as a comma separated list.")
        print("Write 'ALL' to select all probes used in the protocol")
        raw_selected_probes = self.get_input()
        if raw_selected_probes.lower() == "all":
            selected_probes = ph_probes_used_in_protocol
        elif raw_selected_probes.replace(" ", "") == "":  # Empty input
            print("At least one probe needs to be selected. Try again:")
            return self.choose_probes(ph_probes_used_in_protocol)
        else:
            selected_probes = list(raw_selected_probes.replace(" ", "").split(","))
        print(selected_probes)
        return selected_probes

    # Wrapper method, used as mocking in tests for input otherwise do not work
    def get_input(self) -> str:
        return input()

    def record_calibration_data(self, high_ph, high_pH_mv_values, low_pH, low_pH_mv_values, selected_probes):
        # Recording the calibration values
        with open(self.settings["calibration_data_path"], 'r') as file:
            old_calibration_data = yaml.safe_load(file)
            if old_calibration_data is None:
                old_calibration_data = dict()
        for probe in selected_probes:
            old_calibration_data[probe] = {"LowPH": low_pH, "LowPHmV": low_pH_mv_values[probe],
                                           "HighPH": high_ph, "HighPHmV": high_pH_mv_values[probe]}
        with open(self.settings["calibration_data_path"], 'w') as file:
            yaml.safe_dump(old_calibration_data, file)

    def load_settings(self, settings_path: str) -> dict:
        with open(settings_path, 'r') as file:
            return yaml.safe_load(file)

    def live_read_ph(self, protocol_path):
        ph_probes = self.get_probes_used_in_protocol(protocol_path)
        print(f"The following pH probes are used in the protocol {protocol_path}:")
        print(ph_probes)
        print()

        print("Printing the pH's measured by the selected probes, until a key is pressed. "
              "An update will take ~1 second per probe used in the protocol.")
        try:
            while True:
                self.scheduler.getPhOfSelectedProbes(ph_probes)
        except KeyboardInterrupt:
            print("Detected keypress. Stopped printing pH's.")



