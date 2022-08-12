
import threading as th

class KeypressDetector:


    def __init__(self):
        self.has_key_been_pressed = False
        th.Thread(target=self.key_capture_thread, args=(), name='key_capture_thread', daemon=True).start()

    def key_capture_thread(self):
        input()
        self.has_key_been_pressed = True
