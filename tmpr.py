import os
import serial
import serial.tools.list_ports
import time
import sys
from collections import Iterable
from threading import Thread

class worker_tmpr():
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.ser = serial.Serial()
        self.communicating = False
        self.temperatures = [None, None]
        self.output = [None, None]
        self.open_serial()
    def open_serial(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.description == "ttyAMA0":
                continue
            if port.vid ==  0x1fb9:
                self.ser.port = port.device
                self.ser.baudrate = 57600
                self.ser.parity =  serial.PARITY_ODD
                self.ser.bytesize =  serial.SEVENBITS
                self.ser.timeout = 1
                self.ser.write_timeout = 1
                if not self.ser.is_open:
                    try:
                        self.ser.open()
                        time.sleep(1)           # to be changed
                    except:
                        pass
                if self.ser.is_open:
                    print(port.device + ' opened')
                    self.ser.write(b'*idn?')
                    self.ser.flush()
                    break
    def read_temperatures(self):
        for index, letter in zip([0, 1], ['A', 'B']):
            cmd = "rdgst?"
            try:
                resp = self.read(cmd, [letter]).split(';')[-1].strip()
            except:
                resp = None
            if resp == "000":
                cmd = "krdg?"
                try:
                    resp = self.read(cmd, [letter]).split(';')[-1].strip()
                except:
                    resp = None
                if resp != None:
                    self.temperatures[index] = float(resp)
                else:
                    self.temperatures[index] = None
            else:
                self.temperatures[index] = None
                if resp != None and len(resp) == 3:
                    r = int(resp)
                    if r >= 128:
                        app.logger.warning("sensor units overrange for " + letter)
                        r -= 128
                    if r >= 64:
                        app.logger.warning("sensor units zero for " + letter)
                        r -= 64
                    if r >= 32:
                        app.logger.warning("temp overrange for " + letter)
                        r -= 32
                    if r >= 16:
                        app.logger.warning("temp underrange for " + letter)
                        r -= 16
                    if r >= 1:
                        app.logger.warning("invalid reading for " + letter)
                        r -= 1
                    if r > 0:
                        app.logger.warning("unknown temperature reading error for " + letter)
        return
    def read_output(self):
        for index, letter in zip([0, 1], ['1', '2']):
            cmd = "htrst?"
            try:
                resp = self.read(cmd, [letter]).split(';')[-1].strip()
            except:
                resp = None
            if resp == "0":
                cmd = "htr?"
                try:
                    resp = self.read(cmd, [letter]).split(';')[-1].strip()
                except:
                    resp = None
                if resp != None:
                    self.output[index] = float(resp)
                else:
                    self.output[index] = None
            else:
                self.output[index] = None
                if resp != None and len(resp) > 0:
                    r = int(resp)
                    if r == 1:
                        app.logger.warning("heater open load for " + letter)
                    elif r == 2:
                        app.logger.warning("heater short for " + letter)
                    else:
                        app.logger.warning("unknown output state reading error for " + letter)
        return
    def read(self, cmd, payload):
        resp = None
        if self.ser.is_open:
            msg = cmd + '?'
            for item in payload:
                if item == payload[0]:
                    msg += ' '
                else:
                    msg += ','
                msg += item
            msg += '\n'
            try:
                self.ser.write(msg.encode('ascii'))
                self.ser.flush()
                resp = self.ser.readline().decode("ascii")[:-1]
            except:
                self.ser.close()
                self.open_serial()
        else:
            self.open_serial()
        return resp
    def do(self, cmds):
        i = 0
        while self.communicating:
            time.sleep(0.1)
            i += 1
            if i > 30:      # wait for 3 seconds at most
                print("temperature controller is very busy")
                return False
        if self.ser.is_open:
            if isinstance(cmds, Iterable):
                for cmd in cmds:
                    msg = cmd['cmd']
                    for item in cmd['payload']:
                        if item == cmd['payload'][0]:
                            msg += ' '
                        else:
                            msg += ','
                        msg += str(item)
                    # print(msg)
                    msg += '\n'
                    try:
                        self.ser.write(msg.encode('ascii'))
                        self.ser.flush()
                    except:
                        self.ser.close()
                        self.open_serial()
                        self.communicating = False
                        return False
            else:
                print("commands are not iterable")
                self.communicating = False
                return False
        else:
            self.open_serial()
            self.communicating = False
            return False
        self.communicating = False
        return True
    def run(self):
        iterations = 0
        t0 = time.time()
        while iterations < 1024:
            iterations += 1
            try:
                self.communicating = True
                self.read_temperatures()
                print(time.time() - t0, self.temperatures[0])
#                self.read_output()
                self.communicating = False
#                time.sleep(0.25)
            except (KeyboardInterrupt, SystemExit):
                self.communicating = False
                worker_tmpr().stop()
                sys.exit(0)

tmpr = worker_tmpr()
tmpr.run()
