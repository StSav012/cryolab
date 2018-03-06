import serial
import serial.tools.list_ports
import time
import sys
from threading import Thread
from collections import Iterable
import numpy as np
import sounddevice as sd

is_realtime_measurement_running = False

def csv(data, sep = '\t'):
    s = ""
    if isinstance(data, Iterable):
        for line in data:
            l = ""
            if isinstance(line, dict):
                for key, value in line.items():
                    l += repr(value) + sep
            elif isinstance(line, Iterable):
                for item in data:
                    l += repr(item) + sep
            else:
                l = repr(item)
            s += l.strip() + '\n'
    return s

def sine_tone(frequency, duration, volume=1, sample_rate=44100):
    n_samples = int(sample_rate * duration)
    t = np.arange(n_samples) / sample_rate
    sd.play(volume * np.sin(2 * np.pi * frequency * t),
            samplerate=sample_rate,
            blocking=True,
            device='sysdefault')

def snd_notify():
    for i in range(30):
        sine_tone(3135.96, 0.2)
        #sine_tone(2093.00, 0.2)
        sd.sleep(200)

def snd_warning():
    for i in range(4):
        sine_tone(2093.00, 0.2)
        sine_tone(1760.00, 0.2)

class worker(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.ser = serial.Serial()
        self.communicating = False
        self.temperatures = [None, None]
        self.output = [None, None]
        self.pid_data = {1: {}, 2: {}}
        self.error_in = ["", ""]
        self.error_in_sounded = [False, False]
        self.error_out = ["", ""]
        self.error_out_sounded = [False, False]
#        self.open_serial()
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
                    print(port.device, 'opened for the temperature controller')
                    self.ser.write(b'*idn?')
                    self.ser.flush()
                    break
        if not self.ser.is_open:
            time.sleep(1)
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
                    try:
                        temp = float(resp)
                    except:
                        self.temperatures[index] = None
                    else:
                        if self.temperatures[index] != None and temp < 77 and self.temperatures[index] > 77:
                            snd_notify()
                        self.temperatures[index] = temp
                        self.error_in[index] = ""
                        self.error_in_sounded[index] = False
                else:
                    self.temperatures[index] = None
            else:
                self.temperatures[index] = None
                if resp != None and len(resp) == 3:
                    try:
                        r = int(resp)
                    except:
                        pass
                    else:
                        self.error_in[index] = ""
                        if r >= 128:
                            self.error_in[index] = "Sensor units overrange for " + letter
                            r -= 128
                        if r >= 64:
                            if len(self.error_in) > 0:
                                self.error_in[index] += '\n'
                            self.error_in[index] += "Sensor units zero for " + letter
                            r -= 64
                        if r >= 32:
                            if len(self.error_in) > 0:
                                self.error_in[index] += '\n'
                            self.error_in[index] += "Temp overrange for " + letter
                            r -= 32
                        if r >= 16:
                            if len(self.error_in) > 0:
                                self.error_in[index] += '\n'
                            self.error_in[index] += "Temp underrange for " + letter
                            r -= 16
                        if r >= 1:
                            if len(self.error_in) > 0:
                                self.error_in[index] += '\n'
                            self.error_in[index] += "Invalid reading for " + letter
                            r -= 1
                        if r != 0:
                            self.error_in[index] = "Unknown temperature reading error for " + letter
                        app.logger.warning(self.error_in[index])
                        if not self.error_in_sounded[index]:
                            snd_warning()
                            self.error_in_sounded[index] = True
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
                    try:
                        self.output[index] = float(resp)
                    except:
                        self.output[index] = None
                    else:
                        self.error_out[index] = ""
                        self.error_out_sounded[index] = False
                else:
                    self.output[index] = None
            else:
                self.output[index] = None
                if resp != None and len(resp) > 0:
                    try:
                        r = int(resp)
                    except:
                        pass
                    else:
                        if r == 1:
                            self.error_out[index] = "Heater open load for " + letter
                        elif r == 2:
                            self.error_out[index] = "Heater short for " + letter
                        else:
                            self.error_out[index] = "Unknown output state reading error for " + letter
                        app.logger.warning(self.error_out[index])
                        if not self.error_out_sounded[index]:
                            snd_warning()
                            self.error_out_sounded[index] = True
        return
    def pid_turn(self, data):
        try:
            output = data['output']
            ok = True
            if data['action'] == 1:
                ok = ok and (data['mode'] in range(6))
                ok = ok and (data['powerup_enable'] in [0, 1])
                ok = ok and (data['range'] in range(4))
                if data['mode'] != 3:
                    ok = ok and (output in [1, 2])
                    ok = ok and (data['input'] in range(3))
                    ok = ok and self.do("outmode", [output, data['mode'], data['input'], data['powerup_enable']])
                    ok = ok and self.do("pid",     [output, data['P'],    data['I'],     data['D']])
                    ok = ok and self.do("setp",    [output, data['value']])
                else:
                    ok = ok and self.do("outmode", [output, data['mode'], 0, data['powerup_enable']])
                    ok = ok and self.do("mout",    [output, data['manual']])
                ok = ok and self.do("range",   [output, data['range']])
            elif data['action'] == 0:
                ok = ok and (output in [1, 2])
                ok = ok and self.do("outmode", [output, 0, 0, 0])
                ok = ok and self.do("range",   [output, 0])
            else:
                ok = False
        except:
            ok = False
        else:
            if data['action'] == 0:
                self.pid_data[output] = {
                            'input':          self.pid_data[output]['input'] if 'input' in self.pid_data[output] else None,
                            'mode':           None,
                            'powerup_enable': self.pid_data[output]['powerup_enable'] if 'powerup_enable' in self.pid_data[output] else None,
                            'range':          self.pid_data[output]['range'] if 'range' in self.pid_data[output] else None,
                            'value':          self.pid_data[output]['value'] if 'value' in self.pid_data[output] else None,
                            'P':              self.pid_data[output]['P'] if 'P' in self.pid_data[output] else None,
                            'I':              self.pid_data[output]['I'] if 'I' in self.pid_data[output] else None,
                            'D':              self.pid_data[output]['D'] if 'D' in self.pid_data[output] else None,
                            'manual':         self.pid_data[output]['manual'] if 'manual' in self.pid_data[output] else None
                            }
            elif data['action'] == 1:
                if data['mode'] != 3:
                    self.pid_data[output] = {
                                'input':          data['input'],
                                'mode':           data['mode'],
                                'powerup_enable': data['powerup_enable'],
                                'range':          data['range'],
                                'value':          data['value'],
                                'P':              data['P'],
                                'I':              data['I'],
                                'D':              data['D'],
                                'manual':         self.pid_data[output]['manual'] if 'manual' in self.pid_data[output] else None
                                }
                else:
                    self.pid_data[data['output']] = {
                                'input':          self.pid_data[output]['input'] if 'input' in self.pid_data[output] else None,
                                'mode':           data['mode'],
                                'powerup_enable': data['powerup_enable'],
                                'range':          data['range'],
                                'value':          self.pid_data[output]['value'] if 'value' in self.pid_data[output] else None,
                                'P':              self.pid_data[output]['P'] if 'P' in self.pid_data[output] else None,
                                'I':              self.pid_data[output]['I'] if 'I' in self.pid_data[output] else None,
                                'D':              self.pid_data[output]['D'] if 'D' in self.pid_data[output] else None,
                                'manual':         data['manual']
                                }
        return ok
    def read(self, cmd, payload):
        resp = None
        if self.ser.is_open:
            msg = cmd + '?'
            if isinstance(payload, Iterable):
                first_item = True
                for item in payload:
                    if first_item:
                        msg += ' '
                        first_item = False
                    else:
                        msg += ','
                    msg += str(item)
            elif len(payload) > 0:
                msg += ' ' + str(payload)
            msg += '\n'
            try:
                self.ser.write(msg.encode('ascii'))
                self.ser.flush()
                resp = self.ser.readline().decode("ascii")[:-1]
                if len(resp) == 0:
                    self.ser.close()
                    print("restarting " + self.ser.port)
                    self.open_serial()
            except:
                self.ser.close()
                print("restarting " + self.ser.port)
                self.open_serial()
        else:
            self.open_serial()
        return resp
    def do(self, cmd, payload):
        i = 0
        while self.communicating:
            time.sleep(0.1)
            i += 1
            if i > 30:      # wait for 3 seconds at most
                print("temperature controller is very busy")
                return False
        if self.ser.is_open:
            msg = cmd.strip()
            if isinstance(payload, Iterable):
                first_item = True
                for item in payload:
                    if first_item:
                        msg += ' '
                        first_item = False
                    else:
                        msg += ','
                    msg += str(item)
            elif len(payload) > 0:
                msg += ' ' + str(payload)
            # print(msg)
            msg += '\n'
            try:
                self.communicating = True
                self.ser.write(msg.encode('ascii'))
                self.ser.flush()
            except:
                self.ser.close()
                self.open_serial()
                self.communicating = False
                return False
        else:
            self.open_serial()
            self.communicating = False
            return False
        self.communicating = False
        return True
    def run(self):
        global is_realtime_measurement_running
        while True:
            try:
                if not is_realtime_measurement_running:
                    self.communicating = True
                    self.read_temperatures()
                    self.read_output()
                    self.communicating = False
                else:
                    self.temperatures = [None, None]
                    self.output = [None, None]
                time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                self.communicating = False
                self.stop()
                sys.exit(0)

class worker_rtm(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.count = 0
        self.label = 'A'
        self.res = []
        self.paused = True
    def measure(self):
        self.res = []
        global is_realtime_measurement_running
        if is_realtime_measurement_running:
            print("another realtime measurement is running")
            return False
        if not (self.label in ['A', 'B']):
            print("invalid termometer mark:", self.label)
            return False
        i = 0
        while tmpr.communicating:
            time.sleep(0.1)
            i += 1
            if i > 30:      # wait for 3 seconds at most
                print("temperature controller is very busy")
                return False
        is_realtime_measurement_running = True
        print("measurement started")
        init_time = time.time()
        while len(self.res) < self.count:
            try:
                cmd = "rdgst?"
                try:
                    resp = tmpr.read(cmd, [self.label]).split(';')[-1].strip()
                except:
                    resp = None
                if resp == "000":
                    cmd = "krdg?"
                    try:
                        resp = tmpr.read(cmd, [self.label]).split(';')[-1].strip()
                    except:
                        resp = None
                    if resp != None:
                        try:
                            self.res.append({'time': time.time() - init_time, ('temperature' + self.label): float(resp)})
                        except:
                            pass
            except (KeyboardInterrupt, SystemExit):
                sys.exit(0)
        is_realtime_measurement_running = False
        print("measurement finished")
        return True
    def fire(self):
        self.paused = False
    def run(self):
        while True:
            if not self.paused:
                self.measure()
                self.paused = True
            else:
                time.sleep(0.1)

