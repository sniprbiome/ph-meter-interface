import time

import pandas as pd
import serial




class PumpSystem:
    serial_connection = None
    timer = time  # For the purpose of testing.

    def __init__(self, pump_settings: dict):
        self.settings = pump_settings

    def initialize_connection(self) -> None:
        self.serial_connection = serial.Serial(f"COM{self.settings['ComPort']}",
                                               baudrate=self.settings['BaudRate'],
                                               bytesize=serial.EIGHTBITS,
                                               parity=serial.PARITY_NONE,
                                               stopbits=serial.STOPBITS_ONE,
                                               xonxoff=False,
                                               dsrdtr=False,
                                               rtscts=False,
                                               timeout=.5,
                                               )

    def setup_pumps_used_in_protocol(self, protocol: pd.DataFrame):
        pumps = self.get_pumps_used_in_protocol(protocol)
        pump_associated_volumes = self.get_pump_associated_dispention_volume(protocol)
        self.configure_pumps(pumps, pump_associated_volumes)

    # When the program is run, we need to be sure that the pumps have the correct settings.
    def configure_pumps(self, pumps, pump_associated_volumes):
        print(f"Setting up pumps: {pump_associated_volumes}")
        for pump in pumps:
            if not self.has_connection_to_pump(pump):
                raise Exception(f"Connection to pump {pump} could not be established")
            self.send_pump_command(f"{pump} DIA {self.settings['Diameter']}")
            self.send_pump_command(f"{pump} RAT {self.settings['InfusionRate']} MM")
            self.send_pump_command(f"{pump} DIR INF")
            self.send_pump_command(f"{pump} VOL UL")  # Sets the volumes used by the pump to microliters
            self.send_pump_command(f"{pump} CLD INF")
            self.send_pump_command(f"{pump} VOL {pump_associated_volumes[int(pump)]}")

            print(f"Setup of pump {pump} successful")
            print()

    def pump(self, pump_id):
        self.send_pump_command(f"{pump_id} RUN")

    def get_pumps_used_in_protocol(self, protocol: pd.DataFrame) -> list[str]:
        pumps_used = []
        for _, row in protocol.iterrows():
            if row["On/off"] != 0:  # If it is not disabled.
                pumps_used.append(str(row["Pump"]))

        if len(pumps_used) != len(set(pumps_used)):
            raise Exception("The pumps should only be used for one task, see the instruction sheet.")
        return pumps_used

    def send_pump_command(self, command: str) -> None:
        self.serial_connection.dtr = True
        full_command = command + "\r"
        full_command_binary = bytes(full_command, "charmap")
        if self.settings['ShouldPrintPumpMessages']:
            print(f"Send pump command: {full_command_binary}")
        self.serial_connection.write(full_command_binary)
        self.timer.sleep(0.5)  # We need to ensure that the connection isn't overloaded.

    def read_from_pumps(self) -> bytes:
        self.serial_connection.dtr = False
        read_message = self.serial_connection.read_all()
        return read_message

    def has_connection_to_pump(self, pump: str) -> bool:  # TODO does not work correctly
        self.read_from_pumps()  # Removes any noise
        self.send_pump_command(f"{pump} ADR")
        read_message = self.read_from_pumps()
        if self.settings['ShouldPrintPumpMessages']:
            print(read_message)
        return len(read_message) != 0

    def get_pump_associated_dispention_volume(self, protocol: pd.DataFrame) -> dict[int, float]:
        associated_dispensation_volume = {}
        for index, row in protocol.iterrows():
            associated_dispensation_volume[row["Pump"]] = row["Dose vol."]
        return associated_dispensation_volume

    def set_pump_dose_multiplication_factor(self, protocol: pd.DataFrame, dose_multiplication_factor):
        print(f"Setting pump dose multiplcation facotr to {dose_multiplication_factor}")
        pumps = self.get_pumps_used_in_protocol(protocol)
        pump_associated_volumes = self.get_pump_associated_dispention_volume(protocol)
        for pump in pumps:
            self.send_pump_command(f"{pump} VOL {int(pump_associated_volumes[int(pump)]*dose_multiplication_factor)}")

