from email.mime.text import MIMEText
import smtplib, ssl
import yaml


class EmailConnector:

    def __init__(self, settings):
        with open(settings["email"]["EmailSettingsFile"], 'r') as file:
            self.email_settings = yaml.safe_load(file)

    def send_error(self, error_message):
        self.send_mail("Crash", error_message)

    def send_is_done(self, finished_message):
        self.send_mail("Finished run", finished_message)

    def send_mail(self, subject, message: str):

        # Debugging: python -m smtpd -c DebuggingServer -n localhost:1025


        ssl_port = self.email_settings["SSL_PORT"]
        sender_email = self.email_settings["SENDER_EMAIL"]
        password = self.email_settings["EMAIL_PASSWORD"]
        receiver_email = self.email_settings["RECEIVER_EMAIL"]
        smtp_server = self.email_settings["SENDER_SMTP_SERVER"]

        email = MIMEText(message)
        email["From"] = sender_email
        email["Subject"] = subject


        # Create a secure SSL context
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(smtp_server, ssl_port, context=context) as server:
            server.login(sender_email, password)

            server.sendmail(sender_email, [receiver_email], email.as_string())
