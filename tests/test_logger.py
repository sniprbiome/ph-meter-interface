import io
import unittest
from io import StringIO
from unittest.mock import patch

import yaml

import CLI
import Logger
import mock_objects


class Test_Logger(unittest.TestCase):


    def setUp(self):
        self.mock_timer = mock_objects.MockTimer()
        with open('test_config.yml', 'r') as file:
            self.settings = yaml.safe_load(file)
        Logger.standardLogger.timer = self.mock_timer
        Logger.standardLogger.set_enabled(True)

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


