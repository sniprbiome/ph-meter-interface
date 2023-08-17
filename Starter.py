import yaml

from ClientCLI import ClientCLI
import Logger
from Networking.PhysicalSystemServer import PhysicalSystemServer


class Starter:

    def __init__(self, settings_path="config.yml"):
        self.settings = self.load_settings(settings_path)

    def start(self):

        print("Starting CLI")
        print("Settings can be changed in the config.yml file.")

        # We wrap everything in a try, so that we can log all errors that makes the program crash
        try:

            self.printPossibleCommands()

            inputCommand = input()
            if inputCommand == "1":
                cli = ClientCLI(communicate_via_network=False)
                cli.start()
            elif inputCommand == "2":
                server = PhysicalSystemServer(self.settings)
                server.begin_listening()
            elif inputCommand == "3":
                cli = ClientCLI(communicate_via_network=True)
                cli.start()
            else:
                print("Invalid input, try again.")
            pass

        except Exception as e:
            Logger.standardLogger.log(e)
            raise e

    def printPossibleCommands(self):
        print("Options:")
        print(f"1 - Start the program the normal way. Use this if only one instance of a protocol needs to be run at the same time.")
        print(f"2 - Start a pH-meter physical systems server, that manages the pH-meter and the pump system. Only instantiate one server.")
        print(f"3 - Start at pH-meter client. Multiple clients can be started at the same time. The server needs to be started first.")
        print()
        print("Input: ")

    def load_settings(self, settings_path: str) -> dict:
        with open(settings_path, 'r') as file:
            return yaml.safe_load(file)

