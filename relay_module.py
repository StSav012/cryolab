import subprocess
import time
import sys
from threading import Thread

class worker(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.serial = 'QHF2G'
        self.relay = '1'
        self.is_on = None
        self.communicating = False

    def turn(self, on):
        if self.is_on is None:
            return self.is_on
        try:
            i = 0
            while self.communicating and i < 30:
                time.sleep(0.1)
                i += 1
            if self.communicating:
                print('relay module is very busy')
                return None
            cmd = "usbrelay"
            self.communicating = True
            result = subprocess.run([cmd, self.serial + '_' + self.relay + '=' + ('1' if on else '0')], stderr=subprocess.PIPE)
            self.communicating = False
            expected_result = 'Serial: {serial}, Relay: {relay} State: {state} --- Found'.format(serial=self.serial,
                    relay=self.relay, state=('ff' if on else 'fd'))
            state = expected_result in result.stderr.decode('utf-8')
            return state
        except:
            self.communicating = False
            return None

    def run(self):
        while True:
            try:
                self.turn(self.is_on)
                time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                print('caught ctrl+c')
                print("relay module stopped")
                self.join()
                sys.exit(0)

