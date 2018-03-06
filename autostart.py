import serial
import serial.tools.list_ports
import time
import sys
from threading import Thread
from subprocess import Popen, PIPE
import requests

import vacuum_pump
import pressure_gauge

pump = vacuum_pump.pump()

#                pump.do(True)
#                if not(self.pressure is None) and self.pressure < 1e-2:
#                    print("ready to start the compressor")
#                    try:
#                        cmd = "usbrelay QHF2G_1=1"
#                        result = Popen(cmd, shell=True, stdout=PIPE)
#                        time.sleep(1)
#                        r = requests.post("http://localhost/helium_compressor/do", data={'action': 1})
#                        print(r.status_code, r.reason)
#                    except:
#                        pass
#                    sys.exit(0)
#                time.sleep(1)

gauge = pressure_gauge.worker_gauge()
gauge.start()
