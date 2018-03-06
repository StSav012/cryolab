import serial
import serial.tools.list_ports
import time
import sys
from threading import Thread

class worker(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.ser = serial.Serial()
        self.pressure = None
#        self.open_serial()
#        self.run()
    def open_serial(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.description == "ttyAMA0":
                continue
            if port.vid == 0x0451 and port.pid == 0x3410:
                self.ser.port = port.device
                self.ser.baudrate = 9600
                self.ser.parity =  serial.PARITY_NONE
                self.ser.bytesize =  serial.EIGHTBITS
                self.ser.timeout = 1
                self.ser.write_timeout = 1
                try:
                    self.ser.open()
                    time.sleep(1)
                except:
                    pass
                if self.ser.is_open:
                    print('gauge at', port.device, 'opened')
                    break
    def read_pressure(self):
        cmd = "001M^"
        msg = cmd + "\r"
        print("reading pressure from", self.ser.port)
        while self.ser.is_open:
            try:
                self.ser.write(msg.encode('ascii'))
                self.ser.flush()
                resp = self.ser.readline().decode("ascii")
            except:
                continue
            # debug
            if len(resp) == 0:
                self.ser.close()
                print('closing ' + self.ser.port)
                self.open_serial()
                continue
            if len(resp) < 6:
                print("invalid size")
                continue
            m = 0
            e = 0
            i = 0
            cks = 0
            bresp = resp.encode('ascii')
            bcmd = cmd.encode('ascii')
            for c in bresp:
                if i < 4 and bcmd[i] != c:
                    print("invalid beginning")
                if i >= 4 and i < 8:
                    m = m * 10 + c - (b'0')[0]
                elif i >= 8 and i < 10:
                    e = e * 10 + c - (b'0')[0]
                if i < len(resp) - 2:
                    cks += c
                i += 1
            value = m * pow(10., e - 23)
            cks = cks % 64 + 64
            if cks != bresp[len(resp) - 2]:
                print("invalid checksum:", cks)
                continue
            self.pressure = value
            if self.pressure:
                print("Pressure:", self.pressure)
            break
        else:
            self.open_serial()
        return
    def run(self):
        print("pressure gauge started")
        while True:
            try:
                self.read_pressure()
                time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                print("pressure gauge stopped")
#                worker_gauge().stop()
                sys.exit(0)

