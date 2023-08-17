
import threading as th

class KeypressDetector:


    def __init__(self):
        self.has_key_been_pressed = False
        self.listen()

    def key_capture_thread(self):
        input()
        self.has_key_been_pressed = True

    def get_has_key_been_pressed(self) -> bool:
        return self.has_key_been_pressed

    def reset_has_key_been_pressed(self) -> None:
        self.has_key_been_pressed = False
        self.listen()

    def listen(self):
        th.Thread(target=self.key_capture_thread, args=(), name='key_capture_thread', daemon=True).start()
