import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask
from flask import render_template
from flask import jsonify
from flask import request
from flask import send_from_directory
from flask import Response
import os
import serial
import serial.tools.list_ports
import time
import sys
from threading import Thread
import crcmod
import crcmod.predefined
from IPy import IP
from subprocess import Popen, PIPE
from collections import Iterable
import requests
import numpy as np
import sounddevice as sd

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout
import configparser

def get_mac(ip):
    mac = None
    try:
        cmd = "arping -f -I wlan0 " + ip
        result = Popen(cmd, shell=True, stdout=PIPE)
        mac = result.stdout.readlines()[1].decode('ascii').split()[-2][1:-1]
        print(mac)
    except:
        pass
    return mac

config = configparser.ConfigParser()
config.read('/cryolab/python/wsgi.ini')

masters_list = [mac.split('#')[0].strip() for mac in config['masters']['MACs'].splitlines()]

is_realtime_measurement_running = False

def hex2bits(hex_str):
    state = [0 for i in range(len(hex_str) * 4)];
    i = 0
    hex_str = hex_str.upper()
    for char in hex_str:
        c = char.encode('ascii')[0]
        if c < b'0'[0] or (c > b'9'[0] and c < b'A'[0]) or c > b'F'[0]:
            raise ValueError('invalid character %c in %s' % (char, hex_str))
            return
        if c >= b'A'[0]:
            c -= b'A'[0]
        if c >= b'0'[0]:
            c -= b'0'[0]
        for j in range(len(hex_str)):
            if (c & (1 << j)) != 0:
                state[len(hex_str) * 4 - 4 * (i + 1) + j] = 1
        i += 1
    return state

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

class worker_cmpr(Thread):
    crc16 = crcmod.predefined.Crc('modbus')
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.ser = serial.Serial()
        self.communicating = False
        self.temperatures = [None, None, None, None]
        self.pressures = [None, None]
        self.config_mode = None
        self.local_on = None
        self.cold_head_run = None
        self.cold_head_pause = None
        self.fault_off = None
        self.oil_fault_off = None
        self.solenoid_on = None
        self.pressure_off = None
        self.oil_level_alarm = None
        self.water_flow_alarm = None
        self.water_temperature_alarm = None
        self.helium_temperature_off = None
        self.mains_off = None
        self.motor_temperature_off = None
        self.system_on = None
#        self.open_serial()
    def open_serial(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.description == "ttyAMA0":
                continue
            if port.vid == 0x0403 and port.pid == 0x6001:
                self.ser.port = port.device
                self.ser.baudrate = 9600
                self.ser.parity =  serial.PARITY_NONE
                self.ser.bytesize =  serial.EIGHTBITS
                self.ser.timeout = 1
                self.ser.write_timeout = 1
                try:
                    self.ser.open()
                    time.sleep(1)           # to be changed
                except:
                    pass
                break
    def read_temperatures(self):
        cmd = "$TEA"
        while self.ser.is_open:
            crc = self.crc16.new(cmd.encode('ascii'))
            msg = cmd + crc.hexdigest() + '\r'
            try:
                self.ser.write(msg.encode('ascii'))
                self.ser.flush()
                c = self.ser.read(26)
            except:
                continue
            # debug
            if len(c) == 0:
                self.ser.close()
                print('restarting ' + self.ser.port)
                self.open_serial()
                continue
            resp = c.decode("ascii").split(',')
            if resp[0] == "$???":
                continue
            if len(resp) != 6 or resp[0] != cmd:
                self.temperatures = [None, None, None, None]
                print('wrong response: ' + c.decode("ascii"))
                return False
            crc = self.crc16.new(c[:21])
            if crc.hexdigest() != resp[-1][:4]:
                self.temperatures = [None, None, None, None]
                print('wrong crc: ' + c.decode("ascii"))
                return False
            for i in range(len(self.temperatures)):
                self.temperatures[i] = int(resp[i+1])
            break
        else:
            self.open_serial()
        return True
    def read_pressures(self):
        cmd = "$PRA"
        while self.ser.is_open:
            crc = self.crc16.new(cmd.encode('ascii'))
            msg = cmd + crc.hexdigest() + '\r'
            try:
                self.ser.write(msg.encode('ascii'))
                self.ser.flush()
                c = self.ser.read(18)
            except:
                continue
            # debug
            if len(c) == 0:
                self.ser.close()
                print('restarting ' + self.ser.port)
                self.open_serial()
                continue
            resp = c.decode("ascii").split(',')
            if resp[0] == "$???":
                continue
            if len(resp) != 4 or resp[0] != cmd:
                self.pressures = [None, None]
                return False
            crc = self.crc16.new(c[:13])
            if crc.hexdigest() != resp[-1][:4]:
                self.pressures = [None, None]
                return False
            for i in range(len(self.pressures)):
                self.pressures[i] = int(resp[i+1])
            break
        else:
            self.open_serial()
        return True
    def read_status(self):
        cmd = "$STA"
        while self.ser.is_open:
            crc = self.crc16.new(cmd.encode('ascii'))
            msg = cmd + crc.hexdigest() + '\r'
            try:
                self.ser.write(msg.encode('ascii'))
                self.ser.flush()
                c = self.ser.read(15)
            except:
                continue
            # debug
            if len(c) == 0:
                self.ser.close()
                print('restarting ' + self.ser.port)
                self.open_serial()
                continue
            resp = c.decode("ascii").split(',')
            if resp[0] == "$???":
                continue
            if len(resp) != 3 or resp[0] != cmd:
                self.pressures = [None, None]
                return False
            crc = self.crc16.new(c[:10])
            if crc.hexdigest() != resp[-1][:4]:
                self.pressures = [None, None]
                return False
            # normally resp[1] == "0301"
            state = hex2bits(resp[1])
            state_number = state[9] + (state[10] << 1) + (state[11] << 2)
            self.config_mode = state[15]
            self.local_on = bool(state_number == 1)
            self.cold_head_run = bool(state_number == 4)
            self.cold_head_pause = bool(state_number == 5)
            self.fault_off = bool(state_number == 6)
            self.oil_fault_off = bool(state_number == 7)
            self.solenoid_on = bool(state[8])
            self.pressure_off = bool(state[7])
            self.oil_level_alarm = bool(state[6])
            self.water_flow_alarm = bool(state[5])
            self.water_temperature_alarm = bool(state[4])
            self.helium_temperature_off = bool(state[3])
            self.mains_off = bool(state[2])
            self.motor_temperature_off = bool(state[1])
            self.system_on = bool(state[0])
            break
        else:
            self.open_serial()
        return True
    def turn(self, action):
        if action == 0:
            return self.do("$OFF")
        elif action == 1:
            return self.do("$ON1")
        else:
            print("invalid action:", action)
            return False
    def do(self, cmd):
        i = 0
        while self.communicating:
            time.sleep(0.1)
            i += 1
            if i > 30:      # wait for 3 seconds at most
                print("compressor is very busy")
                return False
        while self.ser.is_open:
            self.communicating = True
            crc = self.crc16.new(cmd.encode('ascii'))
            msg = cmd + crc.hexdigest() + '\r'
            try:
                self.ser.write(msg.encode('ascii'))
                self.ser.flush()
                c = self.ser.read(10)
            except:
                continue
            # debug
            if len(c) == 0:
                self.ser.close()
                print('restarting ' + self.ser.port)
                self.open_serial()
                continue
            resp = c.decode("ascii").split(',')
            if resp[0] == "$???":
                continue
            if len(resp) != 2 or resp[0] != cmd:
                self.communicating = False
                return False
            crc = self.crc16.new(c[:5])
            if crc.hexdigest() != resp[-1][:4]:
                self.communicating = False
                return False
            self.communicating = False
            break
        else:
            self.open_serial()
        self.communicating = False
        return True
    def run(self):
        while True:
            try:
                self.communicating = True
                self.read_temperatures()
                self.read_pressures()
                self.read_status()
                self.communicating = False
                time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                self.communicating = False
                worker_cmpr().stop()
                sys.exit(0)

class worker_tmpr(Thread):
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

cmpr = worker_cmpr()
tmpr = worker_tmpr()

class worker_rtm_tmpr(Thread):
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

tmpr_rtm = worker_rtm_tmpr()

trusted_senders = [login.split('#')[0].strip() for login in config['masters']['jabbers'].splitlines()]

class bot(ClientXMPP):

    def __init__(self, jid, password):
        ClientXMPP.__init__(self, jid, password)

        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)
        self.add_event_handler("disconnected", self.disconnected)

        import ssl
        self.ssl_version = ssl.PROTOCOL_TLSv1

    def session_start(self, event):
        try:
            self.send_presence()
            self.get_roster()
        except IqError as err:
            logging.error('There was an error on xmpp session start')
            logging.error(err.iq['error']['condition'])
            self.disconnect()
        except IqTimeout:
            logging.error('Server is taking too long to respond')
            self.disconnect()

    def message(self, msg):
        if str(msg['type']) in ['chat', 'normal'] and len(msg['body']) > 0:
            words = msg['body'].lower().split()
            reply = "Your request was not understood:\n%(body)s" % msg
            sender = str(msg['from']).split('/')[0]
            receiver = str(msg['to']).split('/')[0]
            if sender == receiver:
                return
            try:
                if words[0] == 'about':
                    reply = 'IPM RAS Cryolab setup.\nNizhny Novgorod, Russia.'
                elif words[0] == 'help':
                    reply = '''Possible commands:
about,
help,
compressor [state [verbose] | state {on | off} | pressure | temperatures],
temperature {A | B},
pid {1 | 2} [on {#% | #K {A | B}} | off | range {low | medium | high} | powerup {on | off} | pid #P #I #D]'''
                    if words[1] == 'compressor':
                        reply = '''Possible commands:
compressor,
compressor state,
compressor state verbose,
compressor state on,
compressor state off,
compressor pressure,
compressor temperatures'''
                    elif words[1] == 'temperature':
                        reply = '''Possible commands:
temperature A,
temperature B'''
                    elif words[1] == 'pid':
                        reply = '''Possible commands:
pid {1 | 2} on #K {A | B},
pid {1 | 2} on #%,
pid {1 | 2} off,
pid {1 | 2} range {low | medium | high},
pid {1 | 2} powerup {on | off},
pid {1 | 2} pid #P #I #D'''
                elif words[0] == 'compressor':
                    if cmpr.system_on:
                        reply = 'on'
                    else:
                        reply = 'off'
                    if words[1] in ['state', 'status']:
                        if words[2] in ['on', 'off']:
                            if sender in trusted_senders:
                                if words[2] == 'off':
                                    if cmpr.turn(0):
                                        reply = 'compressor has been turned off'
                                    else:
                                        reply = 'failed to turn off'
                                elif words[2] == 'on':
                                    if cmpr.turn(1):
                                        reply = 'compressor has been turned on'
                                    else:
                                        reply = 'failed to turn on'
                                else:
                                    reply = 'the compressor state cannot be %s' % words[2]
                            else:
                                reply = "You are not authorized."
                                logging.info('%s tried to manipulate' % sender)
                                print('%s tried to manipulate' % sender)
                        elif words[2] == 'verbose':
                                reply  = 'config mode: %s.\n' % repr(cmpr.config_mode)
                                reply += 'local %s, ' % ('on' if cmpr.local_on else 'off')
                                reply += 'system %s, ' % ('on' if cmpr.system_on else 'off')
                                reply += 'solenoid %s.\n' % ('on' if cmpr.solenoid_on else 'off')
                                reply += 'cold head is%s running. ' % ('' if cmpr.cold_head_run else ' not')
                                reply += 'cold head is paused.\n' if cmpr.cold_head_pause else '\n'
                                reply += 'Warning: oil level!\n' if cmpr.oil_level_alarm else ''
                                reply += 'Warning: water flow!\n' if cmpr.water_flow_alarm else ''
                                reply += 'Warning: water temperature!\n' if cmpr.water_temperature_alarm else ''
                                reply += 'Failure: helium temperature!!!\n' if cmpr.helium_temperature_off else ''
                                reply += 'Failure: general fault!!!\n' if cmpr.fault_off else ''
                                reply += 'Failure: oil fault!!!\n' if cmpr.oil_fault_off else ''
                                reply += 'Failure: pressure!!!\n' if cmpr.pressure_off else ''
                                reply += 'Failure: mains!!!\n' if cmpr.mains_off else ''
                                reply += 'Failure: motor temperature!!!' if cmpr.motor_temperature_off else ''
                    elif words[1] in ['temperature', 'temperatures']:
                        reply = '''helium: %d°C,
water out: %d°C,
water in: %d°C''' % (cmpr.temperatures[0], cmpr.temperatures[1], cmpr.temperatures[2])
                    elif words[1] == 'pressure':
                        reply = 'helium: %d psig' % cmpr.pressures[0]
                elif words[0] == 'temperature':
                    if words[1] == 'a':
                        reply = repr(tmpr.temperatures[0])
                    elif words[1] == 'b':
                        reply = repr(tmpr.temperatures[1])
                elif words[0] == 'pid':
                    if words[1] in ['1', '2']:
                        output = int(words[1])
                    elif words[1] == 'all':
                        output = -1
                    else:
                        reply = 'invalid output channel number'
                        raise
                    reply = repr(tmpr.output[output - 1]) + '%'
                    if words[2] in ['range', 'pid', 'powerup', 'on', 'off']:
                        if sender in trusted_senders:
                            if words[2] == 'range':
                                pid_range = 0
                                if words[3].isdecimal():
                                    pid_range = int(words[3])
                                else:
                                    pid_range = ['off', 'low', 'medium', 'high'].index(words[3])
                                if pid_range in [1, 2, 3]:
                                    reply = 'range is set to %s' % ['off', 'low', 'medium', 'high'][pid_range]
                                    tmpr.pid_data[output]['range'] = pid_range
                                else:
                                    reply = 'range cannot be %s' % words[3]
                            elif words[2] == 'pid':
                                pid_p = 0
                                pid_i = 0
                                pid_d = 0
                                try:
                                    pid_p = float(words[3])
                                    pid_i = float(words[4])
                                    pid_d = float(words[5])
                                except:
                                    reply = 'pid parameters cannot be %s, %s, and %s' % words[3], words[4], words[5]
                                else:
                                    tmpr.pid_data[output]['P'] = pid_p
                                    tmpr.pid_data[output]['I'] = pid_i
                                    tmpr.pid_data[output]['D'] = pid_d
                                    reply = 'pid parameters are set to %s, %s, and %s' % words[3], words[4], words[5]
                            elif words[2] == 'powerup':
                                if words[3] in ['off', 'on']:
                                    tmpr.pid_data[output]['powerup_enable'] = ['off', 'on'].index(words[3])
                                    reply = 'powerup is %s' % words[3]
                                else:
                                    reply = 'powerup cannot be %s' % words[3]
                            elif words[2] == 'off':
                                if output == -1:
                                    if tmpr.pid_turn({'output': 1, 'action': 0}) and tmpr.pid_turn({'output': 2, 'action': 0}):
                                        reply = 'all turned off'
                                    else:
                                        reply = 'an error occured while turning off'
                                else:
                                    if tmpr.pid_turn({'output': output, 'action': 0}):
                                        reply = 'turned off'
                                    else:
                                        reply = 'an error occured while turning off'
                            elif words[2] == 'on':
                                if len(words) >= 4:
                                    if words[3].endswith('k'):      # if the desired temperature is set
                                        pid_value = int(words[3].rstrip('k'))
                                        try:
                                            if tmpr.pid_data[output]['range'] == None:
                                                raise
                                            pid_range = tmpr.pid_data[output]['range']
                                        except:
                                            logging.warning('range is not set')
                                            pid_range = 2
                                        try:
                                            if tmpr.pid_data[output]['powerup_enable'] == None:
                                                raise
                                            pid_powerup_enable = tmpr.pid_data[output]['powerup_enable']
                                        except:
                                            logging.warning('powerup is not set')
                                            pid_powerup_enable = 1
                                        try:
                                            if tmpr.pid_data[output]['P'] == None:
                                                raise
                                            pid_p = tmpr.pid_data[output]['P']
                                            if tmpr.pid_data[output]['I'] == None:
                                                raise
                                            pid_i = tmpr.pid_data[output]['I']
                                            if tmpr.pid_data[output]['D'] == None:
                                                raise
                                            pid_d = tmpr.pid_data[output]['D']
                                        except:
                                            logging.warning('pid parameters are not set')
                                            pid_p = 50
                                            pid_i = 20
                                            pid_d = 0
                                        if tmpr.pid_turn({
                                            'output': output,
                                            'action': 1,
                                            'mode': 1,
                                            'input': ['', 'a', 'b'].index(words[4]),
                                            'value': pid_value,
                                            'range': pid_range,
                                            'powerup_enable': pid_powerup_enable,
                                            'P': pid_p,
                                            'I': pid_i,
                                            'D': pid_d
                                            }):
                                            reply = 'turned on to %s on %s' % words[3], words[4].upper()
                                        else:
                                            reply = 'an error occured while turning on to auto'
                                    elif words[3].endswith('%'):    # if the power is set manually
                                        pid_value = int(words[3].rstrip('%'))
                                        try:
                                            if tmpr.pid_data[output]['range'] == None:
                                                raise
                                            pid_range = tmpr.pid_data[output]['range']
                                        except:
                                            logging.warning('range is not set')
                                            pid_range = 2
                                        try:
                                            if tmpr.pid_data[output]['powerup_enable'] == None:
                                                raise
                                            pid_powerup_enable = tmpr.pid_data[output]['powerup_enable']
                                        except:
                                            logging.warning('powerup is not set')
                                            pid_powerup_enable = 1
                                        if tmpr.pid_turn({
                                            'output': output,
                                            'action': 1,
                                            'mode': 3,
                                            'manual': pid_value,
                                            'range': pid_range,
                                            'powerup_enable': pid_powerup_enable
                                            }):
                                            reply = 'turned on to %s' % words[3]
                                        else:
                                            reply = 'an error occured while turning on to manual'
                                    elif words[3] in ['a', 'b']:    # if the sensor comes first
                                        if words[4].endswith('k'):  # if the desired temperature is set
                                            pid_value = int(words[4].rstrip('k'))
                                            try:
                                                if tmpr.pid_data[output]['range'] == None:
                                                    raise
                                                pid_range = tmpr.pid_data[output]['range']
                                            except:
                                                logging.warning('range is not set')
                                                pid_range = 2
                                            try:
                                                if tmpr.pid_data[output]['powerup_enable'] == None:
                                                    raise
                                                pid_powerup_enable = tmpr.pid_data[output]['powerup_enable']
                                            except:
                                                logging.warning('powerup is not set')
                                                pid_powerup_enable = 1
                                            try:
                                                if tmpr.pid_data[output]['P'] == None:
                                                    raise
                                                pid_p = tmpr.pid_data[output]['P']
                                                if tmpr.pid_data[output]['I'] == None:
                                                    raise
                                                pid_i = tmpr.pid_data[output]['I']
                                                if tmpr.pid_data[output]['D'] == None:
                                                    raise
                                                pid_d = tmpr.pid_data[output]['D']
                                            except:
                                                logging.warning('pid parameters are not set')
                                                pid_p = 50
                                                pid_i = 20
                                                pid_d = 0
                                            if tmpr.pid_turn({
                                                'output': output,
                                                'action': 1,
                                                'mode': 1,
                                                'input': ['', 'a', 'b'].index(words[3]),
                                                'value': pid_value,
                                                'range': pid_range,
                                                'powerup_enable': pid_powerup_enable,
                                                'P': pid_p,
                                                'I': pid_i,
                                                'D': pid_d
                                                }):
                                                reply = 'turned on to %s on %s' % words[4].upper(), words[3]
                                            else:
                                                reply = 'an error occured while turning on to auto'
                                        elif words[4].endswith('%'):# if the power is set manually
                                            pid_value = int(words[4].rstrip('%'))
                                            try:
                                                if tmpr.pid_data[output]['range'] == None:
                                                    raise
                                                pid_range = tmpr.pid_data[output]['range']
                                            except:
                                                logging.warning('range is not set')
                                                pid_range = 2
                                            try:
                                                if tmpr.pid_data[output]['powerup_enable'] == None:
                                                    raise
                                                pid_powerup_enable = tmpr.pid_data[output]['powerup_enable']
                                            except:
                                                logging.warning('powerup is not set')
                                                pid_powerup_enable = 1
                                            if tmpr.pid_turn({
                                                'output': output,
                                                'action': 1,
                                                'mode': 3,
                                                'manual': pid_value,
                                                'range': pid_range,
                                                'powerup_enable': pid_powerup_enable
                                                }):
                                                reply = 'turned on to %s' % words[4]
                                            else:
                                                reply = 'an error occured while turning on to manual'
                                        else:
                                            reply = 'an error occured: unknown pid mode'
                                    else:
                                        reply = 'an error occured: unknown pid mode'
                                else:
                                    reply = 'an error occured: too few words'
                        else:
                            reply = "You are not authorized."
                            logging.info('%s tried to manipulate' % sender)
                            print('%s tried to manipulate' % sender)
            except:
                # print('error:', sys.exc_info())
                pass
            msg.reply(reply).send()

    def disconnected(self, data):
        logging.warning('XMPP disconnected')
        print('XMPP disconnected')
        self.disconnect(reconnect=True, send_close=False)

xmpp = bot(config['XMPP']['jid'], config['XMPP']['pass'])
# xmpp.register_plugin('xep_0030') # Service Discovery
# xmpp.register_plugin('xep_0004') # Data Forms
# xmpp.register_plugin('xep_0060') # PubSub
# xmpp.register_plugin('xep_0199') # XMPP Ping
                
xmpp.use_proxy = True
xmpp.proxy_config = {
    'host': config['proxy']['host'],
    'port': int(config['proxy']['port']),
    'username': config['proxy']['username'],
    'password': config['proxy']['password']
}

print("Starting")

app = Flask(__name__)
app.url_map.strict_slashes = False
# app.debug = True
if not app.debug:
    formatter = logging.Formatter("[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")
    handler = TimedRotatingFileHandler('logs/wsgi.log', when='midnight', interval=1, backupCount=5)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)
    app.logger.addHandler(handler)
else:
    logging.basicConfig(level=logging.DEBUG)

if xmpp.connect((config['XMPP']['server'], int(config['XMPP']['port']))):
    print("XMPP connected")
else:
    print("XMPP connection failed")

xmpp.process(block=False)
cmpr.start()
tmpr.start()
tmpr_rtm.start()

@app.errorhandler(404)
def page_not_found(error):
    print('This route does not exist {}'.format(request.url))
    print(error)
    return 'This route does not exist {}'.format(request.url), 404

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/', methods=['GET', 'POST'])
def index():
    if is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    return render_template('status.html',
                           master_mind = (get_mac(request.remote_addr) in masters_list),
                           cmpr_pressures = cmpr.pressures,
                           cmpr_temperatures = cmpr.temperatures,
                           cmpr_config_mode = cmpr.config_mode,
                           cmpr_local_on = cmpr.local_on,
                           cmpr_cold_head_run = cmpr.cold_head_run,
                           cmpr_cold_head_pause = cmpr.cold_head_pause,
                           cmpr_fault_off = cmpr.fault_off,
                           cmpr_oil_fault_off = cmpr.oil_fault_off,
                           cmpr_solenoid_on = cmpr.solenoid_on,
                           cmpr_pressure_off = cmpr.pressure_off,
                           cmpr_oil_level_alarm = cmpr.oil_level_alarm,
                           cmpr_water_flow_alarm = cmpr.water_flow_alarm,
                           cmpr_water_temperature_alarm = cmpr.water_temperature_alarm,
                           cmpr_helium_temperature_off = cmpr.helium_temperature_off,
                           cmpr_mains_off = cmpr.mains_off,
                           cmpr_motor_temperature_off = cmpr.motor_temperature_off,
                           cmpr_system_on = cmpr.system_on,
                           tmpr_temperatures = tmpr.temperatures,
                           tmpr_output = tmpr.output)

@app.route('/json', methods= ['GET'])
def stuff():
    if is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    return jsonify(cmpr_pressures = cmpr.pressures,
                   cmpr_temperatures = cmpr.temperatures,
                   cmpr_config_mode = cmpr.config_mode,
                   cmpr_local_on = cmpr.local_on,
                   cmpr_cold_head_run = cmpr.cold_head_run,
                   cmpr_cold_head_pause = cmpr.cold_head_pause,
                   cmpr_fault_off = cmpr.fault_off,
                   cmpr_oil_fault_off = cmpr.oil_fault_off,
                   cmpr_solenoid_on = cmpr.solenoid_on,
                   cmpr_pressure_off = cmpr.pressure_off,
                   cmpr_oil_level_alarm = cmpr.oil_level_alarm,
                   cmpr_water_flow_alarm = cmpr.water_flow_alarm,
                   cmpr_water_temperature_alarm = cmpr.water_temperature_alarm,
                   cmpr_helium_temperature_off = cmpr.helium_temperature_off,
                   cmpr_mains_off = cmpr.mains_off,
                   cmpr_motor_temperature_off = cmpr.motor_temperature_off,
                   cmpr_system_on = cmpr.system_on,
                   tmpr_temperatures = tmpr.temperatures,
                   tmpr_output = tmpr.output)

@app.route('/helium_compressor')
def cmpr_index():
    if is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    return render_template('cmpr.html',
                           master_mind = (get_mac(request.remote_addr) in masters_list),
                           pressures = cmpr.pressures,
                           temperatures = cmpr.temperatures,
                           config_mode = cmpr.config_mode,
                           local_on = cmpr.local_on,
                           cold_head_run = cmpr.cold_head_run,
                           cold_head_pause = cmpr.cold_head_pause,
                           fault_off = cmpr.fault_off,
                           oil_fault_off = cmpr.oil_fault_off,
                           solenoid_on = cmpr.solenoid_on,
                           pressure_off = cmpr.pressure_off,
                           oil_level_alarm = cmpr.oil_level_alarm,
                           water_flow_alarm = cmpr.water_flow_alarm,
                           water_temperature_alarm = cmpr.water_temperature_alarm,
                           helium_temperature_off = cmpr.helium_temperature_off,
                           mains_off = cmpr.mains_off,
                           motor_temperature_off = cmpr.motor_temperature_off,
                           system_on = cmpr.system_on)

@app.route('/helium_compressor/json', methods= ['GET'])
def cmpr_json():
    return jsonify(pressures = cmpr.pressures,
                   temperatures = cmpr.temperatures,
                   config_mode = cmpr.config_mode,
                   local_on = cmpr.local_on,
                   cold_head_run = cmpr.cold_head_run,
                   cold_head_pause = cmpr.cold_head_pause,
                   fault_off = cmpr.fault_off,
                   oil_fault_off = cmpr.oil_fault_off,
                   solenoid_on = cmpr.solenoid_on,
                   pressure_off = cmpr.pressure_off,
                   oil_level_alarm = cmpr.oil_level_alarm,
                   water_flow_alarm = cmpr.water_flow_alarm,
                   water_temperature_alarm = cmpr.water_temperature_alarm,
                   helium_temperature_off = cmpr.helium_temperature_off,
                   mains_off = cmpr.mains_off,
                   motor_temperature_off = cmpr.motor_temperature_off,
                   system_on = cmpr.system_on)

@app.route('/helium_compressor/do', methods = ['POST'])
def cmpr_do():
    if is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    if get_mac(request.remote_addr) in masters_list:
        try:
            if cmpr.turn(request.form.get('action')):
                return "Command succeeded"
            else:
                return "Command failed"
        except:
            return "Command failed with an error"
    return "Permission denied"

@app.route('/temperature_controller')
def tmpr_index():
    if is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    return render_template('tmpr.html',
                           master_mind = (get_mac(request.remote_addr) in masters_list),
                           temperatures = tmpr.temperatures,
                           output = tmpr.output,
                           rtm  = is_realtime_measurement_running)

@app.route('/temperature_controller/json', methods= ['GET'])
def tmpr_json():
    error = ""
    for index in range(2):
        if len(tmpr.error_in[index]) > 0:
            if len(error) > 0:
                error += '\n'
            error = tmpr.error_in[index]
        if len(tmpr.error_out[index]) > 0:
            if len(error) > 0:
                error += '\n'
            error += tmpr.error_out[index]
    if 'mode' in tmpr.pid_data and tmpr.pid_data['mode'] != None:
        return jsonify(temperatures = tmpr.temperatures,
                       output = tmpr.output,
                       pid = tmpr.pid_data,
                       error = error,
                       rtm = is_realtime_measurement_running)
    else:
        return jsonify(temperatures = tmpr.temperatures,
                       output = tmpr.output,
                       pid = {
                           'input':          None,
                           'mode':           None,
                           'powerup_enable': None,
                           'range':          None,
                           'value':          None,
                           'P':              None,
                           'I':              None,
                           'D':              None,
                           'manual':         None
                           },
                       error = error,
                       rtm = is_realtime_measurement_running)

@app.route('/temperature_controller/temperature/A')
def tmpr_tmpr1():
    if tmpr.temperatures[0] != None:
        return repr(tmpr.temperatures[0])
    else:
        return repr(-1)

@app.route('/temperature_controller/temperature/B')
def tmpr_tmpr2():
    if tmpr.temperatures[1] != None:
        return repr(tmpr.temperatures[1])
    else:
        return repr(-1)

@app.route('/temperature_controller/pid/do', methods = ['POST'])
def tmpr_do():
    if is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    if get_mac(request.remote_addr) in masters_list:
        data = request.json;
        if tmpr.pid_turn(data):
            return "Command succeeded"
        else:
            return "Command failed"
    return "Permission denied"

@app.route('/jokes', methods = ['GET'])
def joke():
    if is_realtime_measurement_running:
        return ""
    url = 'http://www.laughfactory.com/joke/loadmorejokes';
    try:
        r = requests.get(url, params=request.args, timeout=1)
        return r.text
    except:
        return '''{"jokes":[{"joke_text":"I'm not in the mood of joking :("}]}'''

@app.route('/temperature_controller/rtm', methods = ['POST'])
def rtm_tmpr():
    if is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    if get_mac(request.remote_addr) in masters_list:
        try:
            tmpr_rtm.label = request.json.get('label')
            tmpr_rtm.count = int(request.json.get('count'))
        except:
            tmpr_rtm.letter = ''
            tmpr_rtm.count = 0
            return "Measurement failed to start"
        else:
            tmpr_rtm.fire()
            return "Measurement started"
    return "Permission denied"

@app.route('/temperature_controller/rtm/json')
def rtm_tmpr_json():
    return jsonify(data = tmpr_rtm.res)

@app.route('/temperature_controller/rtm/csv')
def rtm_tmpr_csv():
#    print(csv(tmpr_rtm.res))
    return Response(csv(tmpr_rtm.res), mimetype="text/plain")

if __name__ == '__main__':
    print("Running")
#    app.config.update(APPLICATION_ROOT='/')
    try:
        app.run(host='0.0.0.0', port=80, threaded=True)
    except:
        app.run(host='0.0.0.0', threaded=True)

