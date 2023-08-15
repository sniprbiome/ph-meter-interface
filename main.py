import CLI
import Logger

if __name__ == "__main__":

    Logger.standardLogger.set_enabled(True)
    #EmailConnector.test_mail()
    cli = CLI.CLI()
    cli.start()
