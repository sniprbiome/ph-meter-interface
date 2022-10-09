import datetime
import io
import math
import unittest
from io import StringIO
from unittest.mock import patch

import yaml

import CLI
import Logger
import Scheduler
import mock_objects
from PhMeter import PhMeter
from PhysicalSystems import PhysicalSystems


class Test_Logger(unittest.TestCase):


    def setUp(self):
        self.mock_timer = mock_objects.MockTimer()
        with open('test_config.yml', 'r') as file:
            self.settings = yaml.safe_load(file)
        Logger.standardLogger.timer = self.mock_timer
        Logger.standardLogger.set_enabled(True)
        self.fake_file = StringIO()
        Logger.standardLogger.log_file = self.fake_file

    # @patch("Scheduler.Scheduler.select_instruction_sheet", returnvalue=Exception("test"))
    def test_startRun_crashResultsInErrorLogging(self):
        cli = CLI.CLI("test_config.yml")
        fake_file = StringIO()
        Logger.standardLogger.log_file.close()
        Logger.standardLogger.log_file = fake_file
        fake_path = "this_is_a_fake_path"
        try:
            cli.start_run(fake_path)
            self.assertFalse(True)  # It should have crashed
        except Exception:
            fake_file.seek(0)  # reset read position to the start of what has been written
            first_line = fake_file.readline()
            self.assertEqual(first_line, f"-------- LOG AT {self.mock_timer.now()} --------\n")
            # It logged the error!

    def test_readPH_lackOfResponseIsLogged(self):
        with open('test_calibration_data.yml', 'r') as file:
            self.calibration_data = yaml.safe_load(file)
        ph_meter = PhMeter(self.settings['phmeter'], self.calibration_data)
        mock_serial_connection = mock_objects.MockSerialConnection(None)
        ph_meter.serial_connection = mock_serial_connection
        mock_serial_connection.set_write_to_read_list([(b'M\x06\n\x0f\x00\x00"\x8e\r\n', b'')])
        try:
            ph_meter.get_mv_values_of_module("F.0.0.22")
            self.assertFalse(True)  # It should have crashed
        except Exception as e:
            self.fake_file.seek(0)
            first_line = self.fake_file.readline()
            self.assertEqual(first_line, f"-------- LOG AT {self.mock_timer.now()} --------\n")

    def test_measureAssociatedTaskPH_errorIsLogged(self):
        with open('test_calibration_data.yml', 'r') as file:
            self.calibration_data = yaml.safe_load(file)

        physical_system = PhysicalSystems(self.settings)
        scheduler = Scheduler.Scheduler(self.settings, physical_system)
        protocol = Scheduler.select_instruction_sheet("test_protocol.xlsx")
        scheduler.timer = self.mock_timer

        ph_meter = PhMeter(self.settings['phmeter'], self.calibration_data)
        physical_system.ph_meter = ph_meter
        mock_serial_connection = mock_objects.MockSerialConnection(None)
        ph_meter.serial_connection = mock_serial_connection
        ph_meter.timer = self.mock_timer

        start_time = self.mock_timer.now()

        task_queue = scheduler.initialize_task_priority_queue(protocol)
        task_queue.sort(key=lambda x: x.pump_id)

        mock_serial_connection.set_write_to_read_list([(b'M\x06\n\x0f\x00\x01"\x8f\r\n', b''), (b'M\x06\n\x0f\x00\x01"\x8f\r\n', b'')])

        self.assertTrue(math.isnan(scheduler.measure_associated_task_ph(task_queue[0])))
        self.fake_file.seek(0)
        first_line = self.fake_file.readline()
        self.assertEqual(first_line, f"-------- LOG AT {start_time + datetime.timedelta(seconds=1)} --------\n")

