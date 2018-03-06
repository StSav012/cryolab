import serial
import serial.tools.list_ports
import time
import sys
from threading import Thread
import crcmod
import crcmod.predefined
import sounddevice as sd

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
                else:
                    print(self.ser.port, "opened for the helium compressor")
                    break
        if not self.ser.is_open:
            time.sleep(1)
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
        if int(action) == 0:
            return self.do("$OFF")
        elif int(action) == 1:
            return self.do("$ON1")
        else:
            print("invalid action:,", repr(action))
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
                continue
#                self.communicating = False
#                return False
            crc = self.crc16.new(c[:5])
            if crc.hexdigest() != resp[-1][:4]:
                continue
#                self.communicating = False
#                return False
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
                self.stop()
                sys.exit(0)

