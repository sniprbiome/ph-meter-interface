
import unittest

import main
from PH_Meter import PH_Meter
import mock_objects
import yaml

from PumpSystem import PumpSystem
from Scheduler import Scheduler


class Test_PumpSystem(unittest.TestCase):

    pump_system = None
    mock_serial_connection = None

    def setUp(self):
        with open('test_config.yml', 'r') as file:
            settings = yaml.safe_load(file)
        self.scheduler = Scheduler(settings['scheduler'])
        protocol = self.scheduler.select_instruction_sheet("test_protocol.xlsx")
        self.pump_system = PumpSystem(protocol, settings["pumps"])
        self.mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.pump_system.serial_connection = self.mock_serial_connection
        self.pump_system.timer = mock_objects.MockTimer()

    def test_hasCorrectPumpsConnected(self):
        self.assertEqual(["1", "2", "3", "4", "5"], self.pump_system.pumps)

    def test_configurePumpsCorrectly(self):
        self.pump_system.pumps = ["1", "2"] # Just to make testing be shorter
        # Necessary for has_connection_to_pump not to fail:
        # Seven commands per pump
        write_to_read_list = [(b'1 ADR\r', b'connection'), (b'1 DIA 12.45\r', b''), (b'1 RAT 1.0 MM\r', b''), (b'1 DIR INF\r', b''), (b'1 VOL UL\r', b''), (b'1 CLD INF\r', b''), (b'1 VOL 50\r', b''),
                              (b'2 ADR\r', b'connection'), (b'2 DIA 12.45\r', b''), (b'2 RAT 1.0 MM\r', b''), (b'2 DIR INF\r', b''), (b'2 VOL UL\r', b''), (b'2 CLD INF\r', b''), (b'2 VOL 10\r', b'')]
        self.mock_serial_connection.set_write_to_read_list(write_to_read_list)
        self.pump_system.configure_pumps()
        expected_commands = [b'1 ADR\r', b'1 DIA 12.45\r', b'1 RAT 1.0 MM\r', b'1 DIR INF\r', b'1 VOL UL\r', b'1 CLD INF\r', b'1 VOL 50\r',
                             b'2 ADR\r', b'2 DIA 12.45\r', b'2 RAT 1.0 MM\r', b'2 DIR INF\r', b'2 VOL UL\r', b'2 CLD INF\r', b'2 VOL 10\r']

        print(self.mock_serial_connection.written_commands)
        self.assertEqual(expected_commands, self.mock_serial_connection.written_commands)

    def test_hasConnectionToPump(self):
        self.mock_serial_connection.set_write_to_read_list([(b'1 ADR\r', b'haha'), (b'2 ADR\r', b'hahaha'), (b'3 ADR\r', b'')])
        self.assertTrue(self.pump_system.has_connection_to_pump(1))
        self.assertTrue(self.pump_system.has_connection_to_pump(2))
        self.assertFalse(self.pump_system.has_connection_to_pump(3))  # No connection to pump 3

    def test_actualPumping(self):
        self.mock_serial_connection.set_write_to_read_list([(b'1 RUN\r', b'Ran 1'), (b'2 RUN\r', b'Ran 2')])
        self.pump_system.pump(1)
        self.pump_system.pump(2)
        self.assertEqual([b'1 RUN\r', b'2 RUN\r'], self.mock_serial_connection.written_commands)