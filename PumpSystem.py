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
        for pump in self.pumps:
            self.test_has_connection_to_pump(pump)
            self.send_pump_command(f"{pump} DIA {self.pump_diameter}")
            self.send_pump_command(f"{pump} RAT {self.infusion_rate}")
            self.send_pump_command(f"{pump} DIR INF")
            self.send_pump_command(f"{pump} VOL UL")  # Sets the volumes used by the pump to milliliters
            self.send_pump_command(f"{pump} CLD INF")
            self.send_pump_command(f"{pump} VOL {self.pump_associated_volumes[pump]}")
            #TODO write comments for this

    def pump(self, pump_id, dose_volume):
        print("test")
        raise NotImplementedError()

    def pumps_used_in_protocol(self, protocol):
        pumps_used = map(str, protocol["Pump"].tolist())
        if len(pumps_used) != set(pumps_used):
            raise Exception("The pumps should only be used for one task, see the instruction sheet.")
        return pumps_used

    def send_pump_command(self, command):
        self.serial_connection.dtr = True
        full_command = command + "\n"
        full_command_binary = bytes(full_command, "charmap")
        self.serial_connection.write(full_command_binary)
        time.sleep(0.5)  # We need to ensure that the connection isnøt overloaded.

    def test_has_connection_to_pump(self, pump):
        raise NotImplementedError()

    def get_pump_associated_dispention_volume(self, protocol):
        associated_dispention_volume = {}
        for index, row in protocol.iterrows():
            associated_dispention_volume[row["Pumo"]] = row["Dose vol."]
        return associated_dispention_volume

