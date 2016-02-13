import socket
import time
import sys

TCP_IP = '192.168.0.12'
TCP_PORT = 1394
BUFFER_SIZE = 256
POWER_LINE_FREQUENCY = 50

def query(s, cmd):
    msg = cmd.strip() + "\n"
    s.send(msg.encode("ascii"))
    data = ""
    if cmd.split()[0].endswith("?"):
        c = b' '
        while c[0] >= 10 and len(data) < BUFFER_SIZE - 1:
            try:
                c = s.recv(1)
                data += c.decode("ascii")
            except:
                break
        return data.strip()
    else:
        return None

def remote_query(s, cmd):
#    if cmd.strip().lower() != "*rst" and query(s, "SOUR:PDEL:NVPR?") != "1":
#        if query(s, "SOUR:PDEL:NVPR?") != "1":          # check again
#            raise IOError("No suitable Model 2182A with the correct firmware revision is properly connected to the RS-232 port")
    msg = "SYST:COMM:SER:SEND \"" + cmd.strip() + "\""
    query(s, msg)
    ret_msg = ""
    if cmd.split()[0].endswith("?"):
        data = query(s, "SYST:COMM:SER:ENT?")
        n = 0
        while len(data) == 0 and n < 42:
            data = query(s, "SYST:COMM:SER:ENT?")
            n += 1
        ret_msg += data.strip()
        print("data len =", len(data), "cmd =", cmd)
        while len(data) == BUFFER_SIZE - 2:
            data = query(s, "SYST:COMM:SER:ENT?")
            ret_msg += data.strip()
            print("data len =", len(data), "cmd =", cmd)
        return ret_msg
    else:
        return None

print("connecting to %s:%d" % (TCP_IP, TCP_PORT))
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect((TCP_IP, TCP_PORT))
except:
    print("failed to connect %s:%d" % (TCP_IP, TCP_PORT))
    sys.exit(0)
else:
    print("connected to %s:%d" % (TCP_IP, TCP_PORT))
s.settimeout(0.25)

def iv_curve(s, num=1):
    query(s, "*RST")                            # Restores 6221 defaults.

    cmds_rem_start = [
        "VOLT:RANG 10",
        "volt:nplc 0.1"
    ]
    for cmd in cmds_rem_start:
        remote_query(s, cmd)

    INT = 5
    COUNT = 251
    CURR_HIGH = 50e-3
    CURR_LOW = 0
    PULSE_WIDTH = 6e-4
    SOURCE_DELAY = 2e-4
    CURR_BIAS = 0
    CURR_START = CURR_LOW
    CURR_STOP = CURR_HIGH
    CURR_STEP = (CURR_STOP - CURR_START) / (COUNT - 1)
    CURR_DELAY = INT/POWER_LINE_FREQUENCY
    SWEEP = True

    cmds_start = [
        "SOUR:CURR:COMP 3",                             # Sets compliance to 3V.
        "SOUR:CURR " + repr(CURR_BIAS),                 # Set bias current to CURR_BIAS.
        "SOUR:PDEL:HIGH " + repr(CURR_HIGH),            # Sets pulse high value to CURR_HIGH.
        "SOUR:PDEL:LOW " + repr(CURR_LOW),              # Sets pulse low value to CURR_LOW.
        "SOUR:PDEL:WIDT " + repr(PULSE_WIDTH),          # Sets pulse width to PULSE_WIDTH.
        "SOUR:PDEL:SDEL " + repr(SOURCE_DELAY),         # Sets source delay to SOURCE_DELAY.
        "SOUR:PDEL:COUN " + repr(COUNT),                # Sets pulse count to COUNT.
        "SOUR:PDEL:RANG BEST",                          # Selects the best source range for fixed output.
        "SOUR:SWE:RANG BEST",                           # Selects the best source range for sweep.
        "SOUR:SWE:SPAC LIN",                            # Selects linear staircase sweep.
        "SOUR:CURR:STAR " + repr(CURR_START),           # Sets start current to CURR_START.
        "SOUR:CURR:STOP " + repr(CURR_STOP),            # Sets stop current to CURR_STOP.
        "SOUR:CURR:STEP " + repr(CURR_STEP),            # Sets step current to CURR_STEP.
        "SOUR:DEL " + repr(CURR_DELAY),                 # Sets delay to CURR_DELAY.
        "SOUR:SWE:COUN 1",                              # Sets sweep count to 1.
        "SOUR:SWE:CAB ON",                              # Enables compliance abort.
        "SOUR:PDEL:SWE " + ("ON" if SWEEP else "OFF"),  # Enables or disables sweep function.
        "SOUR:PDEL:INT " + repr(INT),                   # Sets pulse interval to INT PLC (power line cycles) = INT × (1/50) s.
        "SOUR:PDEL:LME 2",                              # Sets for two low pulse measurements.
                             # Sets buffer size to COUNT points. Should be the same as Pulse Delta count.
        "UNIT V",                                       # Selects measurement unit.
    ]
    for cmd in cmds_start:
        query(s, cmd)

    for xxx in range(num):
        query(s, "TRAC:CLE"),                           # Clears buffer of readings.
        query(s, "TRAC:FEED:CONT NEXT"),                # Enables buffer.
        query(s, "SOUR:PDEL:ARM")                       # Arms Pulse Delta.
        while not query(s, "SOUR:PDEL:ARM?") == "1":
            time.sleep(0.1)
        query(s, "INIT:IMM")                            # Starts Pulse Delta measurements.
        time.sleep(COUNT * INT / POWER_LINE_FREQUENCY)
        query(s, "SOUR:SWE:ABOR")
        query(s, "FORM:ELEM READ,SOUR")
    #   print(query(s, "TRAC:DATA:TYPE?"))
        data = query(s, "TRAC:DATA?").split(',')
        n = 0
        for u, i in zip(data[0::2], data[1::2]):
            n += 1
            print(n, '\t', i, u)
    #cmds_calc = [
    #    "CALC2:FORM MEAN",                              # Selects the mean buffer calculation.
    #    "CALC2:STAT ON",                                # Enables buffer calculation.
    #    "CALC2:IMM",                                    # Performs the mean calculation.
    #]
    #for cmd in cmds_calc:
    #    query(s, cmd)
    #print(query(s, "CALC2:DATA?"))                      # Requests the result of the mean calculation.

print("ready to start")
iv_curve(s, 3)
print("done")

s.close()
print("connection closed")

