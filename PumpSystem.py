import functools
import time

import serial




class PumpSystem:
    serial_connection = None

    def __init__(self, protocol, pump_settings):
        self.pumps = self.pumps_used_in_protocol(protocol)
        self.pump_associated_volumes = self.get_pump_associated_dispention_volume(protocol)
        self.comport = "COM" + str(pump_settings["ComPort"])
        self.baud_rate = pump_settings["BaudRate"]
        self.pump_diameter = pump_settings["Diameter"]
        self.infusion_rate = pump_settings["InfusionRate"]

    def initialize_connection(self):
        self.serial_connection = serial.Serial(self.comport,
                                               baudrate=self.baud_rate,
                                               bytesize=serial.EIGHTBITS,
                                               parity=serial.PARITY_NONE,
                                               stopbits=serial.STOPBITS_ONE,
                                               xonxoff=False,
                                               dsrdtr=False,
                                               rtscts=False,
                                               timeout=.5,
                                               )

    # When the program is run, we need to be sure that the pumps have the correct settings.
    def configure_pumps(self):
        print(f"Setting up pumps: {self.pumps}")
        for pump in self.pumps:
            if not self.has_connection_to_pump(pump):
                raise Exception(f"Connection to pump {pump} could not be established")
            self.send_pump_command(f"{pump} DIA {self.pump_diameter}")
            self.send_pump_command(f"{pump} RAT {self.infusion_rate} MM")
            self.send_pump_command(f"{pump} DIR INF")
            self.send_pump_command(f"{pump} VOL UL")  # Sets the volumes used by the pump to microliters
            self.send_pump_command(f"{pump} CLD INF")
            self.send_pump_command(f"{pump} VOL {self.pump_associated_volumes[int(pump)]}")



    def pump(self, pump_id, dose_volume):
        print("test")
        raise NotImplementedError()

    def pumps_used_in_protocol(self, protocol):
        pumps_used = list(map(str, protocol["Pump"].tolist()))
        if len(pumps_used) != len(set(pumps_used)):
            raise Exception("The pumps should only be used for one task, see the instruction sheet.")
        return pumps_used

    def send_pump_command(self, command):
        self.serial_connection.dtr = True
        full_command = command + "\r"
        full_command_binary = bytes(full_command, "charmap")
        print(f"Send pump command: {full_command_binary}")
        self.serial_connection.write(full_command_binary)
        time.sleep(0.5)  # We need to ensure that the connection isn't overloaded.

    def read_from_pumps(self):
        self.serial_connection.dtr = False
        read_message = self.serial_connection.read_all()
        return read_message


    def has_connection_to_pump(self, pump):
        self.send_pump_command(f"{pump} ADR")
        read_message = self.read_from_pumps()
        return len(read_message) != 0
        #self.send_pump_command("5 VER")
        #self.read_from_pumps()

        #raise NotImplementedError()

    def get_pump_associated_dispention_volume(self, protocol):
        associated_dispention_volume = {}
        for index, row in protocol.iterrows():
            associated_dispention_volume[row["Pump"]] = row["Dose vol."]
        return associated_dispention_volume

