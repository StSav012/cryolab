import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask
from flask import render_template
from flask import jsonify
from flask import request
from flask import send_from_directory
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

masters_list = ["00:13:77:AD:CD:39", "00:21:63:99:F6:83",
                "D4:3D:7E:05:14:27", # anfertev
                "00:24:1D:29:F4:F1", # rls
                "00:21:91:54:80:76", # experiment
                "D4:3D:7E:BF:46:C9"  # alp
               ]

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

app = Flask(__name__)
app.debug = False
if not app.debug:
    formatter = logging.Formatter("[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")
    handler = TimedRotatingFileHandler('logs/wsgi.log', when='midnight', interval=1, backupCount=5)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)
    log.addHandler(handler)
    app.logger.addHandler(handler)
if __name__ == '__main__':
    app.run(host='0.0.0.0')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def index():
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

@app.route('/cmpr_do', methods = ['POST'])
def cmpr_do():
    if get_mac(request.remote_addr) in masters_list:
        if cmpr.do(request.form.get('cmd')):
            return "Command " + request.form['cmd'] + " succeeded"
        else:
            return "Command " + request.form['cmd'] + " failed"
    return "Permission denied"

@app.route('/temperature_controller')
def tmpr_index():
    return render_template('tmpr.html',
                           master_mind = (get_mac(request.remote_addr) in masters_list),
                           temperatures = tmpr.temperatures,
                           output = tmpr.output)

@app.route('/temperature_controller/json', methods= ['GET'])
def tmpr_json():
    return jsonify(temperatures = tmpr.temperatures,
                   output = tmpr.output)

@app.route('/tmpr_do', methods = ['POST'])
def tmpr_do():
    if get_mac(request.remote_addr) in masters_list:
        if tmpr.do(request.json.get('cmds')):
            return "Commands succeeded"
        else:
            return "Commands failed"
    return "Permission denied"

@app.route('/jokes', methods = ['GET'])
def joke():
    url = 'http://www.laughfactory.com/joke/loadmorejokes';
    try:
        r = requests.get(url, params=request.args, timeout=1)
        return r.text
    except:
        return '''{"jokes":[{"joke_text":"I'm not in the mood of joking :("}]}'''

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
        self.open_serial()
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
                if len(resp) == 0:
                    self.ser.close()
                    self.open_serial()
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
        while True:
            try:
                self.communicating = True
                self.read_temperatures()
                self.read_output()
                self.communicating = False
                time.sleep(0.25)
            except (KeyboardInterrupt, SystemExit):
                self.communicating = False
                worker_tmpr().stop()
                sys.exit(0)

cmpr = worker_cmpr()
tmpr = worker_tmpr()
cmpr.start()
tmpr.start()
