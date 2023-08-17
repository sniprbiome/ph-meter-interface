import ClientCLI
import Logger
import Starter

if __name__ == "__main__":

    Logger.standardLogger.set_enabled(True)
    starter = Starter.Starter()
    starter.start()
    # cli = ClientCLI.ClientCLI()
    # cli.start()
