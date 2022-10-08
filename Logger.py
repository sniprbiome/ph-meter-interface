

import datetime
import traceback

# Works as a static class
from typing import TextIO


class Logger:

    enabled = False
    log_file: TextIO = None
    timer = datetime.datetime

    def Logger(self):
        pass

    def log(self, exception: Exception):
        if self.enabled and self.log_file is not None:
            exception_traceback = exception.__traceback__
            tb_lines = [line.rstrip('\n') for line in
                        traceback.format_exception(exception.__class__, exception, exception_traceback)]
            current_time = self.timer.now()
            self.log_file.write(f"-------- LOG AT {current_time} --------\n")
            self.log_file.writelines(tb_lines)
            self.log_file.write("\n")

    def set_logging_path(self, path: str):
        # Will add the time the path is set so that one is able to discern between different log files.
        timer_string: str = str(datetime.datetime.now()).replace(":", "_")
        full_path = f"{path}_{timer_string}.log"
        if self.log_file is not None:
            self.log_file.close()
        self.log_file = open(full_path, "w")
        print()

    def set_enabled(self, value):
        self.enabled = value

# The static instance
standardLogger = Logger()