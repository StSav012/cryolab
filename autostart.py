import time
from threading import Thread

import vacuum_pump
import relay_module
import helium_compressor

class worker(Thread):
    def __init__(self, relay, pump, compressor):
        Thread.__init__(self)
        self.relay = relay
        self.pump = pump
        self.cmpr = compressor
        self.relay_on = False
        self.water_cold = False
        self.pump_on = False
        self.pump_ready = False
        self.compressor_on = False
        self._running = False
        self.daemon = True

    def set_running(self, running):
        self.relay_on = False
        self.water_cold = False
        self.pump_on = False
        self.pump_ready = False
        self.compressor_on = False
        self._running = running
        print('autostart ' + ('en' if running else 'dis') + 'abled')

    def is_running(self):
        return self._running

    def run(self):
        while True:
            while not self._running:
                time.sleep(1)
            self.relay_on = False
            self.water_cold = False
            self.pump_on = False
            self.pump_ready = False
            self.compressor_on = False
            self.relay.is_on = True
            while self._running and not self.relay.turn(on=True):
                time.sleep(1)
            if not self._running:
                continue
            self.relay_on = True
            print('relay is on')
            time.sleep(5)
            while self._running and not self.pump.turn(turn_on=True):
                time.sleep(1)
            if not self._running:
                continue
            self.pump_on = True
            print('pump is on')
            time.sleep(5)
            while self._running and self.pump.speed and self.pump.speed < 80000:
                time.sleep(1)
            if not self._running:
                continue
            self.pump_ready = True
            print('pump is ready')
            while self._running and (not self.cmpr.temperatures[1] or self.cmpr.temperatures[1] > 20
                    or not self.cmpr.temperatures[2] or self.cmpr.temperatures[2] > 20):
                time.sleep(1)
            if not self._running:
                continue
            self.water_cold = True
            print('water is cold')
            while self._running and not self.cmpr.turn(action=1):
                time.sleep(1)
            if not self._running:
                continue
            self.compressor_on = True
            print('compressor is on')
            self._running = False

