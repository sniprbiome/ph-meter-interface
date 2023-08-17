import unittest
import yaml

from Networking import EmailConnector
from ClientCLI import ClientCLI
from PhysicalSystems import PhysicalSystems
from Scheduler import Scheduler
from tests import mock_objects
from unittest.mock import patch


def test_exception(_):
    raise Exception("This is a test exception.")

class Test_email_connector(unittest.TestCase):

    def setUp(self):
        with open('test_config.yml', 'r') as file:
            self.settings = yaml.safe_load(file)
        self.email_connector = EmailConnector.EmailConnector(self.settings)
        self.mock_email_server = mock_objects.MockEmailServer("testsender@test.com", "smtp.test.com",
                                                              "thisisnotthebestpasswordintheworld", 465,
                                                              "testreciever@test.com")

        self.cli = ClientCLI("test_config.yml")
        self.cli.timer = mock_objects.MockTimer
        self.physical_system = PhysicalSystems(self.settings)
        self.scheduler = Scheduler(self.settings, self.physical_system)


    @patch("smtplib.SMTP_SSL")
    def test_send_simple_email(self, mock_server):
        mock_server.return_value = self.mock_email_server
        self.mock_email_server.emails_received.clear()
        # Kage
        self.email_connector.send_mail("A test", "Simple email")
        self.assertEqual(1, len(self.mock_email_server.emails_received))
        expected_email = 'Content-Type: text/plain; charset="us-ascii"\nMIME-Version: 1.0' \
                         '\nContent-Transfer-Encoding: 7bit\nFrom: testsender@test.com\nSubject: A test\n\nSimple email'
        self.assertEqual(("testsender@test.com", "testreciever@test.com", expected_email), self.mock_email_server.emails_received[0])

    @patch("smtplib.SMTP_SSL")
    @patch("Scheduler.Scheduler.start", return_value="kage") # Just assume it works
    def test_email_on_finished_run(self, _, mock_server):
        mock_server.return_value = self.mock_email_server
        self.mock_email_server.emails_received.clear()
        self.cli.start_run("fake_protocol")
        self.assertEqual(1, len(self.mock_email_server.emails_received))
        expected_email = 'Content-Type: text/plain; charset="us-ascii"\nMIME-Version: 1.0\n' \
                         'Content-Transfer-Encoding: 7bit\nFrom: testsender@test.com\n' \
                         'Subject: Finished run\n\nRun of protocol "fake_protocol" has successfully finished'
        self.assertEqual(('testsender@test.com', 'testreciever@test.com', expected_email), self.mock_email_server.emails_received[0])


    @patch("smtplib.SMTP_SSL")
    @patch("Scheduler.Scheduler.start", wraps=test_exception)
    def test_email_on_failed_run(self, mock_run, mock_server):
        mock_server.return_value = self.mock_email_server
        self.mock_email_server.emails_received.clear()
        try:
            self.cli.start_run("fake_protocol")
        except Exception as e:
            self.assertEqual(1, len(self.mock_email_server.emails_received))
            print(self.mock_email_server.emails_received[0])
            expected_partial_email = 'Content-Type: text/plain; charset="us-ascii"\nMIME-Version: 1.0\n' \
                             'Content-Transfer-Encoding: 7bit\nFrom: testsender@test.com\n' \
                             'Subject: Crash\n\nRun of protocol "fake_protocol" failed with error: This is a test exception., ' \
                             'Traceback (most recent call last):\n '
            self.assertEqual(('testsender@test.com', 'testreciever@test.com'), (self.mock_email_server.emails_received[0][0], self.mock_email_server.emails_received[0][1]))
            self.assertTrue(expected_partial_email in self.mock_email_server.emails_received[0][2])
        else:
            self.assertFalse(True)