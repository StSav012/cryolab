import sys
from IPy import IP
from subprocess import Popen, PIPE

def get_mac(ip):
    try:
        IP(ip)
        cmd = "arping -I wlan0 -f " + ip
        result = Popen(cmd, shell=True, stdout=PIPE)
        mac = result.stdout.readlines()[1].decode('ascii').split()[-2][1:-1]
        return mac
    except:
        return None

print(get_mac("192.168.213.8"))

