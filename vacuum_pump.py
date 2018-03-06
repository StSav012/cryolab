import serial
import serial.tools.list_ports
import time
import sys

class pump():
    true = '1' * 6
    false = '0' * 6
    parameter_pump_on = 10
    def __init__(self):
        self.ser = serial.Serial()
        self.address = 1
        self.open_serial()
    def checksum(self, cmd):
        csk = 0
        for c in cmd.encode('ascii'):
            csk += c
        return csk % 256
    def make_cmd(self, cmd_code, payload = '=?'):
        cmd  = ('%03d' % self.address)
        cmd += ('0' if payload == '=?' else '1') + '0'
        cmd += ('%03d' % cmd_code)
        cmd += ('%02d' % len(payload))
        if len(cmd) != 10:
            print('incorrect command forming:', cmd)
            return None
        cmd += payload
        cmd += ('%03d' % self.checksum(cmd))
        cmd += '\r'
        return cmd
    def open_serial(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.description == "ttyAMA0":
                continue
            if port.vid ==  0x1a86:
                self.ser.port = port.device
                self.ser.baudrate = 9600
                self.ser.parity =  serial.PARITY_NONE
                self.ser.bytesize =  serial.EIGHTBITS
                self.ser.timeout = 1
                self.ser.write_timeout = 1
                if not self.ser.is_open:
                    try:
                        self.ser.open()
                        time.sleep(self.ser.timeout)
                    except:
                        pass
                if self.ser.is_open:
                    print(port.device + ' opened for the vacuum pump')
                    break

    def set_bool(self, parameter, value):
        msg = self.make_cmd(parameter, (self.true if value else self.false))
        if self.ser.is_open:
            try:
                while self.ser.is_open:
                    self.ser.write(msg.encode('ascii'))
                    self.ser.flush()
                    resp = self.ser.readline().decode("ascii")
                    # check for validity: the response should match the command
                    if resp == msg:
                        print('request understood')
                        return True
                    elif resp[10:16] in ['NO_DEF', '_RANGE', '_LOGIC']:
                        print('the pump returned an error:', resp[10:16])
                        print('as a response to', msg)
                        return False
                    else:
                        print('incorrect response:', resp.encode('ascii'))
                    time.sleep(self.ser.timeout)
            except:
                self.ser.close()
                self.open_serial()
        else:
            self.open_serial()
        return False

    def get_bool(self, parameter):
        msg = self.make_cmd(parameter)
        if self.ser.is_open:
            try:
                while self.ser.is_open:
                    self.ser.write(msg.encode('ascii'))
                    self.ser.flush()
                    resp = self.ser.readline().decode("ascii")
                    # check for validity: checksum and value
                    if len(resp) != 20 or self.checksum(resp[:16]) != int(resp[16:19]):
                        print('incorrect response:', resp.encode('ascii'))
                        continue
                    if resp[10:16] in [self.true, self.false]:
#                        print('response:', resp.encode('ascii'))
                        return resp[10:16] == self.true
                    elif resp[10:16] in ['NO_DEF', '_RANGE', '_LOGIC']:
                        print('the pump returned an error:', resp[10:16])
                        print('as a response to', msg)
                        return None
                    else:
                        print('incorrect response:', resp.encode('ascii'))
                    time.sleep(self.ser.timeout)
            except:
                self.ser.close()
                self.open_serial()
        else:
            self.open_serial()
        return None

    def turn(self, turn_on):
        return self.set_bool(self.parameter_pump_on, turn_on)

    def is_on(self):
        return self.get_bool(self.parameter_pump_on)
