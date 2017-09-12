import serial
import serial.tools.list_ports
import time
ser = serial.Serial()
ports = serial.tools.list_ports.comports()
if len(ports) > 0:
    for port in ports:
        if port.description == "ttyAMA0":
            continue
        print(port.device)
        print(port.description)
        print(port.hwid)
        # print(repr(port.vid), repr(port.pid))
        print("Manufacturer: " + port.manufacturer)
        # print(port.product)
        # print(port.interface)
        ser.port = port.device
        # ser.baudrate = 9600
        # ser.parity =  serial.PARITY_NONE
        # ser.bytesize =  serial.EIGHTBITS
        # ser.timeout = 1
        # ser.write_timeout = 1
        try:
            ser.open()
            if not ser.is_open:
                print("failed to open port")
            else:
                ser.close()
        except:
            pass
print("done")
