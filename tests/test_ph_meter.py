
import unittest

import yaml

from PH_Meter import PH_Meter
import mock_objects


class TestPH_Meter(unittest.TestCase):

    ph_meter = None
    mock_serial_connection = None

    def setUp(self):
        with open('test_config.yml', 'r') as file:
            settings = yaml.safe_load(file)

        with open('test_calibration_data.yml', 'r') as file:
            self.calibration_data = yaml.safe_load(file)
            if self.calibration_data is None:
                self.calibration_data = dict()
        self.ph_meter = PH_Meter(settings['phmeter'], self.calibration_data)
        self.mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.ph_meter.serial_connection = self.mock_serial_connection

    def test_sendRequestMVCommand(self):
        self.mock_serial_connection.set_write_to_read_list([(b'M\x06\n\x0f\x01\x00"\x8f\r\n', b'\x10\x11\x12')])
        self.ph_meter.send_request_mv_command("F.1.0.22")
        self.assertEqual(self.mock_serial_connection.read_all(), b'\x10\x11\x12')
        self.assertTrue(self.mock_serial_connection.dtr)

    def test_readMvResult_correctIDGiven(self):
        self.mock_serial_connection.read_buffer = b'P\x0E\x10\x0f\x01\x00"\x00\x00\x01\x01\x10\x10\x12\x34\x00\x0D\x0A'
        read_result = self.ph_meter.read_mv_result()
        self.assertEqual(read_result.recipient, b'P')
        self.assertEqual(read_result.length_of_reply, b'\x0E')
        self.assertEqual(read_result.command_acted_upon, b'\x10')
        self.assertEqual(read_result.data, b'\x00\x00\x01\x01\x10\x10\x12\x34')
        self.assertEqual(read_result.reply_device_id, [b'\x0f', b'\x01', b'\x00', b'"'])
        # TODO also look at checksum

    def test_bytesToMvValue(self):
        self.assertEqual(0, self.ph_meter.get_mv_value_from_bytes(b'\x00'[0], b'\x00'[0]))
        self.assertAlmostEqual(70.7, self.ph_meter.get_mv_value_from_bytes(b'\x02'[0], b'\xC3'[0]))
        self.assertAlmostEqual(-70.7, self.ph_meter.get_mv_value_from_bytes(b'\xFD'[0], b'\x3D'[0]))

    def test_getPhValueFromMVResponse(self):
        self.mock_serial_connection.read_buffer = b'P\x0E\x10\x0f\x01\x00"\x00\x00\x02\xC3\xFD\x3D\x00\x00\x00\x0D\x0A'
        mock_response = self.ph_meter.read_mv_result()
        self.calibration_data["F.1.0.22_1"] = {"HighPH": 9.0, "HighPHmV": -114.29, "LowPH": 4, "LowPHmV": 171.43}
        self.calibration_data["F.1.0.22_2"] = {"HighPH": 9.0, "HighPHmV": -114.29, "LowPH": 4, "LowPHmV": 171.43}
        self.calibration_data["F.1.0.22_3"] = {"HighPH": 9.0, "HighPHmV": -114.29, "LowPH": 4, "LowPHmV": 171.43}
        self.calibration_data["F.1.0.22_4"] = {"HighPH": 9.0, "HighPHmV": -114.29, "LowPH": 4, "LowPHmV": 171.43}
        self.assertAlmostEqual(7.0, self.ph_meter.get_ph_value_of_probe_from_mv_response(mock_response, "F.1.0.22_1"), 2)
        self.assertAlmostEqual(5.76, self.ph_meter.get_ph_value_of_probe_from_mv_response(mock_response, "F.1.0.22_2"), 2)
        self.assertAlmostEqual(14 - 5.76, self.ph_meter.get_ph_value_of_probe_from_mv_response(mock_response, "F.1.0.22_3"), 2)  # Inverted voltage of above
        self.assertAlmostEqual(7.0, self.ph_meter.get_ph_value_of_probe_from_mv_response(mock_response, "F.1.0.22_4"), 2)

    def test_measure_ph_with_probe(self):
        self.calibration_data["F.1.0.22_2"] = {"HighPH": 9.0, "HighPHmV": -114.29, "LowPH": 4, "LowPHmV": 171.43}
        self.mock_serial_connection.set_write_to_read_list([(b'M\x06\n\x0f\x01\x00"\x8f\r\n', b'P\x0E\x10\x0f\x01\x00"\x00\x00\x02\xC3\xFD\x3D\x00\x00\x00\x0D\x0A')])
        self.assertAlmostEqual(5.76, self.ph_meter.measure_ph_with_probe("F.1.0.22_2"), 2)

    def test_handles_1_missing_serial_output(self):
        self.calibration_data["F.1.0.22_2"] = {"HighPH": 9.0, "HighPHmV": -114.29, "LowPH": 4, "LowPHmV": 171.43}
        self.mock_serial_connection.set_write_to_read_list([(b'M\x06\n\x0f\x01\x00"\x8f\r\n', b'P\x0E\x10'), # First output is invalid, it will have to try to measure again
                                                            (b'M\x06\n\x0f\x01\x00"\x8f\r\n', b'P\x0E\x10\x0f\x01\x00"\x00\x00\x02\xC3\xFD\x3D\x00\x00\x00\x0D\x0A')])
        self.assertAlmostEqual(5.76, self.ph_meter.measure_ph_with_probe("F.1.0.22_2"), 2)


    def test_handles_error_at_2_missing_serial_output(self):
        self.calibration_data["F.1.0.22_2"] = {"HighPH": 9.0, "HighPHmV": -114.29, "LowPH": 4, "LowPHmV": 171.43}
        self.mock_serial_connection.set_write_to_read_list([(b'M\x06\n\x0f\x01\x00"\x8f\r\n', b'P\x0E\x10'), # First output is invalid, it will have to try to measure again
                                                            (b'M\x06\n\x0f\x01\x00"\x8f\r\n', b'P\x0E\x10'), # Second is also invalid
                                                            (b'M\x06\n\x0f\x01\x00"\x8f\r\n', b'P\x0E\x10\x0f\x01\x00"\x00\x00\x02\xC3\xFD\x3D\x00\x00\x00\x0D\x0A')])
        with self.assertRaises(Exception):
            self.ph_meter.measure_ph_with_probe("F.1.0.22_2")