import os
import traceback
from tkinter.filedialog import askopenfilename
from typing import List

import yaml
import pandas

import Logger
from KeypressDetector import KeypressDetector
from Networking.PhysicalSystemsClient import PhysicalSystemsClient
from PhMeter import PhReadException
from PhysicalSystems import PhysicalSystems
from Scheduler import Scheduler
from Networking import EmailConnector


class ClientCLI:

    def __init__(self, settings_path="config.yml", communicate_via_network=False):
        self.settings = self.load_settings(settings_path)
        Logger.standardLogger.set_logging_path(self.settings["protocol_path"])
        if communicate_via_network:
            self.physical_systems = PhysicalSystemsClient(self.settings)
        else:
            self.physical_systems = PhysicalSystems(self.settings)
        self.email_connector = EmailConnector.EmailConnector(self.settings)

    def start(self):

        print("Starting CLI")
        print("Settings can be changed in the config.yml file.")

        # We wrap everything in a try, so that we can log all errors that makes the program crash
        try:

            print("Initializing ph meter connection and pump system connection.")
            self.physical_systems.initialize_systems()

            protocol_path = self.settings["protocol_path"]

            while True:
                self.printPossibleCommands(protocol_path)

                inputCommand = self.get_input()

                print()

                if inputCommand == "1":
                    protocol_path = self.set_protocol_used_for_run()
                elif inputCommand == "2":
                    self.calibrate_ph_probes(protocol_path)
                elif inputCommand == "3":
                    self.start_run(protocol_path)
                    break
                elif inputCommand == "4":
                    self.assign_pump_ids()
                elif inputCommand == "5":
                    self.restart_failed_run(protocol_path)
                    break
                elif inputCommand == "6":
                    self.live_read_ph(protocol_path)
                elif inputCommand == "7":
                    self.pump_liquid(protocol_path)
                elif inputCommand == "8":
                    print("Exiting program.")
                    break
                else:
                    print("Viable input not given. Try again.")

                print()
        except Exception as e:
            Logger.standardLogger.log(e)
            raise e

    def start_run(self, protocol_path: str) -> None:
        try:
            scheduler = Scheduler(self.settings, self.physical_systems)
            scheduler.start(protocol_path)
        except Exception as e:
            Logger.standardLogger.log(e)
            if self.settings["email"]["ShouldSendEmail"]:
                self.email_connector.send_error(f"Run of protocol \"{protocol_path}\" failed with error: {str(e)}, {traceback.format_exc()}")
                print("Has send email with error")
            raise e
        print("Run has finished")
        if self.settings["email"]["ShouldSendEmail"]:
            self.email_connector.send_is_done(f"Run of protocol \"{protocol_path}\" has successfully finished")
            print("Has send email repporting finished run")

    def printPossibleCommands(self, protocol_path: str) -> None:
        print("Options:")
        print(f"1 - Set protocol used for run. Currently \"{protocol_path}\".")
        print("2 - Calibrate ph-measuring probes. Old calibration data will be used if this is not done.")
        print("3 - Run selected protocol.")
        print("4 - Assign new ID's for the pumps.")
        print("5 - Restart failed run.")
        print("6 - Live read pH. pH will be measured using all probes in the selected protocol.")
        print("7 - Pump liquid. Useful after the liquid in the syringes have been changed.")
        print("8 - Exit program.")
        print()
        print("Input:")

    def restart_failed_run(self, protocol_path: str) -> None:
        print("Enter the name of the saved run data, or write ”stop” to go back:")
        filename = self.get_input()
        if filename == "stop":
            return
        elif not os.path.exists(filename):
            print(f"The file: {filename} did not exist. Try again.")
            self.restart_failed_run(protocol_path)
        print(f"The run ”{filename}” will be restarted based on the protocol: {protocol_path}")

        scheduler = Scheduler(self.settings, self.physical_systems)
        scheduler.restart_run(protocol_path, filename)

    def assign_pump_ids(self) -> None:
        print("Plug the main cable from the computer into the pump you want to assign an ID.")
        print("Then write the ID you want to assign the pump. Must be from 1 to 99.")
        print("Write STOP when you want to stop assigning ID's")
        while True:
            print("Input: ")
            input_code = self.get_input()
            if input_code.lower() == "stop":
                break
            elif input_code.lower() == "measure":
                print(f"Current pump has address: {self.physical_systems.get_current_pump_address()}")
            else:
                print(f"It now has the address: {self.physical_systems.set_and_get_address_for_current_pump(int(input_code))}")
        print("Stopped assigning ID's.")

    def set_protocol_used_for_run(self) -> str:
        selected_protocol = askopenfilename()
        print(f"Selected protocol: {selected_protocol}")
        # We also change the logging path
        Logger.standardLogger.set_logging_path(selected_protocol)
        return selected_protocol

    def calibrate_ph_probes(self, selected_protocol_path: str) -> None:
        ph_probes_used_in_protocol = self.get_probes_used_in_protocol(selected_protocol_path)

        selected_probes = self.choose_probes(ph_probes_used_in_protocol)
        probes_to_pumps = self.get_probe_to_pump(selected_probes, selected_protocol_path)
        low_pH_mv_values, low_pH = self.get_ph_calibration_values("low", selected_probes, probes_to_pumps)
        high_pH_mv_values, high_ph = self.get_ph_calibration_values("high", selected_probes, probes_to_pumps)
        self.record_calibration_data(high_ph, high_pH_mv_values, low_pH, low_pH_mv_values, selected_probes)
        self.physical_systems.recalibrate_ph_meter()
        print("Calibration finished.")

    def get_probes_used_in_protocol(self, selected_protocol_path: str) -> list[str]:
        if os.path.exists(selected_protocol_path):
            selected_protocol = pandas.read_excel(selected_protocol_path)
            ph_probes_used_in_protocol: list[str] = list(set(selected_protocol["pH probe"].to_list()))
            ph_probes_used_in_protocol.sort()
            return ph_probes_used_in_protocol
        else:
            return []

    def get_ph_calibration_values(self, ph_level: str, selected_probes: List[str], probes_to_pumps: dict[str, str]) -> (dict[str, float], float):
        print(f"Place the probes in a buffer with a {ph_level} pH. Enter the pH of this buffer:")

        ph = self.get_input()

        print("The mV readings of the ph probes in the buffer need to stabilize.")
        print("Wait until the mV values for the pH probes have stabilized.")
        print("The values will be printed to the console. This will take about ~1 second per selected probe.")
        print("Press a key when the values have stabilized to continue. It will then update the values one final time.")

        detector = KeypressDetector()
        pH_mv_values = self.physical_systems.get_mv_values_of_selected_probes(selected_probes)
        while not detector.get_has_key_been_pressed():
            self.pretty_print_pH_mV_values(pH_mv_values, probes_to_pumps)
            pH_mv_values = self.physical_systems.get_mv_values_of_selected_probes(selected_probes)

        print(f"The final mV values for the different probes are: {pH_mv_values}")

        return pH_mv_values, float(ph)

    def choose_probes(self, ph_probes_used_in_protocol: list[str]) -> list[str]:
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
        print(f"The selected probes are: {selected_probes}")
        return selected_probes

    # Wrapper method, used as mocking in tests for input otherwise do not work
    def get_input(self) -> str:
        return input()

    def record_calibration_data(self, high_ph: float, high_pH_mv_values: dict[str, float],
                                      low_pH: float, low_pH_mv_values: dict[str, float], selected_probes: list[str]) -> None:
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

    def live_read_ph(self, protocol_path: str):
        ph_probes = self.get_probes_used_in_protocol(protocol_path)
        print(f"The following pH probes are used in the protocol {protocol_path}:")
        print(ph_probes)
        print()

        print("Printing the pH's measured by the selected probes, until a key is pressed. "
              "An update will take ~1 second per probe used in the protocol.")
        detector = KeypressDetector()

        while not detector.has_key_been_pressed:
            try:
                ph_values = self.physical_systems.get_ph_values_of_selected_probes(ph_probes)
            except PhReadException:
                print("Error when trying to read pH values from the pH meter. "
                      "Try checking the probe connections if this continues. Retrying...")
                continue
            except Exception:
                print("Unknown error occurred. Will attempt to read probe pH values again...")
                continue

            probes_to_pumps = self.get_probe_to_pump(ph_probes, protocol_path)
            self.pretty_print_pH_mV_values(ph_values, probes_to_pumps)

        print("A key has been pressed. Stopped live-reading pH values.")

    def pretty_print_pH_mV_values(self, ph_values: dict[str, float], probe_to_pump):
        rounded_ph_values = {k: "{:.2f}".format(v) for k, v in ph_values.items()}
        rounded_ph_values_with_pump = {(f"pump {probe_to_pump[k]}"): v for k, v in rounded_ph_values.items()}
        print(rounded_ph_values_with_pump)

    def get_probe_to_pump(self, ph_probes, protocol_path):
        protocol = pandas.read_excel(protocol_path)
        probe_to_pump = {}
        for probe in ph_probes:
            rows_with_probe = protocol[protocol["pH probe"] == probe]  # Normally only one
            associated_pump = rows_with_probe["Pump"].iloc[0]
            probe_to_pump[probe] = associated_pump
        return probe_to_pump

    def pump_liquid(self, protocol_path: str):
        pumps_used_in_protocol = self.get_pumps_used_in_protocol(protocol_path)
        pumps_chosen = self.choose_pumps(pumps_used_in_protocol)
        pump_amount = self.choose_pump_amount()
        self.pump(pumps_chosen, pump_amount)

    def choose_pumps(self, pumps_used_in_protocol: list[str]) -> list[str]:
        print(f"The following pumps are used in the selected protocol: {pumps_used_in_protocol}")
        print(f"Select the pumpd to be used by writing them as a comma separated list.")
        print("Write 'ALL' to select all probes used in the protocol")
        raw_selected_pumps = self.get_input()
        if raw_selected_pumps.lower() == "all":
            selected_probes = pumps_used_in_protocol
        elif raw_selected_pumps.replace(" ", "") == "":  # Empty input
            print("At least one pumps needs to be selected. Try again:")
            return self.choose_probes(pumps_used_in_protocol)
        else:
            pumps_used_in_protocol = list(raw_selected_pumps.replace(" ", "").split(","))
        print(f"The selected pumps are: {pumps_used_in_protocol}")
        return pumps_used_in_protocol

    def get_pumps_used_in_protocol(self, protocol_path: str):
        if os.path.exists(protocol_path):
            selected_protocol = pandas.read_excel(protocol_path)
            pumps_used_in_protocol: list[str] = list(set(selected_protocol["Pump"].to_list()))
            pumps_used_in_protocol.sort()
            return pumps_used_in_protocol
        else:
            return []

    def choose_pump_amount(self) -> int:
        print("How many times should be pumped? Note that the pumps needs to have been set up before this. Write integer.")
        pump_amount_raw = self.get_input()
        pump_amount = int(pump_amount_raw)
        return pump_amount

    def pump(self, pumps_chosen, pump_amount):
        for pump in pumps_chosen:
            print(f"Pumping with pump {pump}.")
            self.physical_systems.pump_n_times(pump, pump_amount)
