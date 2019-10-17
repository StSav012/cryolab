import serial
import serial.tools.list_ports
import time
import sys
from threading import Thread

class worker(Thread):
    true = 0x31
    false = 0x30
    parameter_pump_on = b'000'
    parameter_status = b'205'
    parameter_speed_hz = b'203'

    def __init__(self):
        Thread.__init__(self)
        self.ser = serial.Serial()
        self.address = 0
        self.pumping = None
        self.speed = None
        self.communicating = False
        self.daemon = True
#        self.open_serial()
    
    def _checksum(self, cmd):
        csk = cmd[1]
        for c in cmd[2:]:
            csk ^= c
        return format(csk, 'X').encode('ascii')
    
    def _make_cmd(self, cmd_code, payload = b''):
        if len(cmd_code) != 3:
            # print('incorrect command code:', cmd_code)
            return None
        cmd  = bytes([0x02])
        cmd += bytes([0x80 + self.address])
        cmd += cmd_code
        cmd += bytes([self.true if payload else self.false])
        cmd += payload
        cmd += bytes([0x03])
        cmd += self._checksum(cmd)
        return cmd

    def _block(self):
        i = 0
        while self.communicating:
            time.sleep(0.1)
            i += 1
            if i > 30:      # wait for 3 seconds at most
                # print("pump is very busy")
                return False
        return True
    
    def open_serial(self):
        self.communicating = False
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
                    except (serial.SerialException, TypeError):
                        pass
                    finally:
                        time.sleep(self.ser.timeout)
                if self.ser.is_open:
                    print(port.device + ' opened for the vacuum pump')
                    break

    def set_bool(self, parameter, value):
        if not self._block():
            # print("pump is very busy")
            return None
        msg = self._make_cmd(parameter, bytes([self.true if value else self.false]))
        if self.ser.is_open:
            try:
                self.communicating = True
                self.ser.write(msg)
                self.ser.flush()
                time.sleep(1 if self.ser.timeout is None else self.ser.timeout)
                resp = self.ser.read(6)
                self.ser.flush()
                self.communicating = False
                # print('response:', resp)
                # check for validity
                if len(resp) != 6 or self._checksum(resp[:-2]) != resp[-2:]:
                    # print('incorrect response', resp, 'to', msg)
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                    return None
                elif resp[2] == 6:
                    # print('request acknowledged')
                    return True
                else:
                    # print('the pump returned code', hex(resp[2]), 'as a response to', msg)
                    return False
            except:
                try:
                    self.ser.close()
                except (serial.SerialException, TypeError):
                    print("can't close", self.ser.port)
                    pass
                self.open_serial()
        else:
            self.open_serial()
        return False

    def get_bool(self, parameter):
        if not self._block():
            print("pump is very busy")
            return None
        msg = self._make_cmd(parameter)
        if self.ser.is_open:
            try:
                self.communicating = True
                self.ser.write(msg)
                self.ser.flush()
                time.sleep(1 if self.ser.timeout is None else self.ser.timeout)
                resp = self.ser.read(10)
                self.ser.flush()
                self.communicating = False
                # check for validity: _checksum and value
                # print('response:', resp)
                if len(resp) == 6 and self._checksum(resp[:-2]) == resp[-2:]:
                    # print('command', msg, 'failed with code', hex(resp[2]))
                    return None
                if len(resp) != 10 or resp[:6] != msg[:6] or self._checksum(resp[:-2]) != resp[-2:]:
                    # print('incorrect response', resp, 'to', msg)
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                    return None
                if resp[6] in [self.true, self.false]:
                    return resp[6] == self.true
                else:
                    # print('incorrect response', resp, 'to', msg)
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                    return None
            except (serial.SerialException, TypeError):
                try:
                    self.ser.close()
                except:
                    print("can't close", self.ser.port)
                    pass
                self.open_serial()
        else:
            self.open_serial()
        return None

    def get_int6(self, parameter):
        if not self._block():
            print("pump is very busy")
            return None
        msg = self._make_cmd(parameter)
        if self.ser.is_open:
            try:
                self.communicating = True
                self.ser.write(msg)
                self.ser.flush()
                time.sleep(1 if self.ser.timeout is None else self.ser.timeout)
                resp = self.ser.read(15)
                self.ser.flush()
                self.communicating = False
                # check for validity: checksum and value
                # print('response:', resp)
                if len(resp) == 6 and self._checksum(resp[:-2]) == resp[-2:]:
                    # print('command', msg, 'failed with code', hex(resp[2]))
                    return None
                if len(resp) != 15 or resp[:6] != msg[:6] or self._checksum(resp[:-2]) != resp[-2:]:
                    # print('incorrect response', resp, 'to', msg)
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                    return None
                else:
                    try:
                        return int(resp[6:12])
                    except (TypeError, ValueError):
                        # print('incorrect response', resp, 'to', msg)
                        self.ser.reset_input_buffer()
                        self.ser.reset_output_buffer()
                        return None
            except:
                try:
                    self.ser.close()
                except (serial.SerialException, TypeError):
                    print("can't close", self.ser.port)
                    pass
                self.open_serial()
        else:
            self.open_serial()
        return None

    def turn(self, turn_on):
        return self.set_bool(self.parameter_pump_on, turn_on)

    def is_on(self):
        return self.get_bool(self.parameter_pump_on) and self.get_int6(self.parameter_status) in [2, 5]

    def get_speed_hz(self):
        return self.get_int6(self.parameter_speed_hz)

    def run(self):
        while True:
            try:
                self.pumping = self.is_on()
                self.speed = self.get_speed_hz()
                if self.speed:
                    self.speed *= 60.
                time.sleep(1 if self.ser.timeout is None else self.ser.timeout)
            except (KeyboardInterrupt, SystemExit):
                print('caught ctrl+c')
                try:
                    self.ser.close()
                except (serial.SerialException, TypeError):
                    pass
                self.communicating = False
                self.join()
                sys.exit(0)

