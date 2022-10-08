import CLI
import Logger
import PhysicalSystems

if __name__ == "__main__":

    Logger.standardLogger.set_enabled(True)
    cli = CLI.CLI()
    cli.start()
