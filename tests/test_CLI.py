import unittest
from unittest.mock import patch, MagicMock

import serial
import yaml

from CLI import CLI
from PhMeter import PhMeter
from PhysicalSystems import PhysicalSystems
from Scheduler import Scheduler

import mock_objects


# For a test
mock_input = ["F.0.1.13_3, F.0.1.22_1", 4, 7]
def mock_get_input():
    return_value = mock_input[0]
    mock_input.pop(0)
    return return_value

class TestBase(unittest.TestCase):

    def setUp(self) -> None:
        with open('test_config.yml', 'r') as file:
            self.settings = yaml.safe_load(file)
        self.cli = CLI("test_config.yml")

        self.cli.timer = mock_objects.MockTimer
        self.physical_system = PhysicalSystems(self.settings)
        self.scheduler = Scheduler(self.settings, self.physical_system)

    @patch("serial.Serial", return_value=mock_objects.MockSerialConnection(None))
    def test_getMVAtSelectedProbes(self, mock: MagicMock):
        serial_connection: mock_objects.MockSerialConnection = mock.return_value
        serial_connection.set_write_to_read_list([(b'M\x06\n\x0f\x00\x01\x13\x80\r\n', b'P\x0E\x10\x0f\x00\x01\x13\x00\x00\x02\xC3\xFD\x3D\x00\x00\x00\x0D\x0A'),
                                                  (b'M\x06\n\x0f\x00\x01"\x8f\r\n', b'P\x0E\x10\x0f\x00\x01"\x01\x08\x02\xC3\xFD\x3D\x00\x00\x00\x0D\x0A')])

        selected_probes = ["F.0.1.13_3", "F.0.1.22_1"]  # Do not use a set as the order matters
        self.physical_system.initialize_systems()
        mvValues = self.physical_system.get_mv_values_of_selected_probes(selected_probes)
        self.assertEqual({"F.0.1.22_1": 26.4, "F.0.1.13_3": -70.7}, mvValues)

    @patch("serial.Serial", return_value=mock_objects.MockSerialConnection(None))
    @patch("time.sleep", return_value=None)
    @patch("CLI.CLI.get_input", side_effect=["F.0.1.7_3, F.0.1.8_1", 4, 7])
    @patch("KeypressDetector.KeypressDetector.get_has_key_been_pressed", side_effect=[True, True]) # Otherwise it will run forever
    def test_calibrate_ph_probes(self, mock ,  mock1: MagicMock, mock2: MagicMock, mock_serial: MagicMock):
        serial_connection: mock_objects.MockSerialConnection = mock_serial.return_value
        self.settings["calibration_data_path"] = "test_calibration_data_specific.yml"
        self.cli.settings = self.settings
        with open(self.settings["calibration_data_path"], "r+") as file:  # Clear the file so we can see the changes we make.
            file.truncate()

        serial_connection.set_write_to_read_list([(b'M\x06\n\x0f\x00\x01\x07t\r\n', b'P\x0E\x10\x0f\x00\x01\x13\x00\x00\x02\xC3\x0F\x3D\x00\x00\x00\x0D\x0A'),
                                                  (b'M\x06\n\x0f\x00\x01\x08u\r\n', b'P\x0E\x10\x0f\x00\x01"\x01\x08\x02\xC3\xFD\x3D\x00\x00\x00\x0D\x0A'),
                                                  (b'M\x06\n\x0f\x00\x01\x07t\r\n', b'P\x0E\x10\x0f\x00\x01\x13\x00\x00\x02\xC3\xFD\x3D\x00\x00\x00\x0D\x0A'),
                                                  (b'M\x06\n\x0f\x00\x01\x08u\r\n', b'P\x0E\x10\x0f\x00\x01"\x02\x08\x02\xC3\xFD\x3D\x00\x00\x00\x0D\x0A'),                                                  ] )
        self.physical_system = PhysicalSystems(self.settings)
        self.cli.physical_systems = self.physical_system
        self.physical_system.initialize_systems()
        self.cli.calibrate_ph_probes("test_calibration_protocol.xlsx")

        with open(self.settings["calibration_data_path"], 'r') as file:
            calibration_data_result = yaml.safe_load(file)
            expected_result = {'F.0.1.7_3': {'HighPH': 7, 'HighPHmV': -70.7, 'LowPH': 4, 'LowPHmV': 390.1},
                               'F.0.1.8_1': {'HighPH': 7, 'HighPHmV': 52.0 , 'LowPH': 4, 'LowPHmV': 26.4}}

            self.assertEqual(expected_result, calibration_data_result)

    @patch("CLI.CLI.get_input", return_value="All")
    def test_get_probes_to_calibrate_ALL(self, _):
        probes_used = ["test1", "test2", "test3"]
        probes_to_calibrate = self.cli.choose_probes(probes_used)
        self.assertCountEqual(probes_used, probes_to_calibrate)

    @patch("CLI.CLI.get_input", return_value="F.0.1.13_3")
    def test_get_probes_to_calibrate_1_input(self, _):
        probes_used = ["test1", "test2", "test3"]
        probes_to_calibrate = self.cli.choose_probes(probes_used)
        self.assertCountEqual(["F.0.1.13_3"], probes_to_calibrate)

    @patch("CLI.CLI.get_input", return_value="F.0.1.13_3, F.0.1.22_4, F.1.1.12_1")
    def test_get_probes_to_calibrate_multi_input(self, _):
        probes_used = ["test1", "test2", "test3"]
        probes_to_calibrate = self.cli.choose_probes(probes_used)
        self.assertCountEqual(["F.0.1.13_3", "F.0.1.22_4", "F.1.1.12_1"], probes_to_calibrate)

    @patch("CLI.CLI.get_input", side_effect=["", "", "", "F.0.1.13_3, F.0.1.22_1"])
    def test_get_probes_to_calibrate_no_input(self, _):
        probes_used = ["test1", "test2", "test3"]
        # It should retry when no input is given
        probes_to_calibrate = self.cli.choose_probes(probes_used)
        self.assertCountEqual(["F.0.1.13_3", "F.0.1.22_1"], probes_to_calibrate)
