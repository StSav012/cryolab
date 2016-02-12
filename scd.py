import socket
import time
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import subprocess

TCP_IP = '192.168.0.12'
TCP_PORT = 1394
BUFFER_SIZE = 256
POWER_LINE_FREQUENCY = 50

WAVE_FREQ = 1
WAVE_DCYC = 100
CURR_HIGH = 2.0e-6
CURR_LOW = 0
PM = False
DURATION = 10 / WAVE_FREQ
COUNT = 60
COMPLIANCE = 3

TOTAL_COUNT = DURATION * WAVE_FREQ * COUNT
if TOTAL_COUNT > 1024:
    raise "too many points"
APER = 0.1 / (WAVE_FREQ * COUNT)
DELAY = 1

THRES_U = 2.1
REPETITIONS = 5

def query(s, cmd, remote=False):
    print("issued", cmd)
    msg = cmd.strip() + "\n"
    s.send(msg.encode("ascii"))
    data = b''
    if cmd.split()[0].endswith("?"):
        c = b' '
        while len(data) < BUFFER_SIZE - 1:
            try:
                c = s.recv(1)
                if c[0] in [b'\n'[0], b'\r'[0]]:
                    if len(data) == 0:
                        continue
                    elif len(data) == BUFFER_SIZE - 2:
                        print("response ended")
                        break
                    if remote:
                        remote = False
                    else:
                        print("response ended")
                        break
                else:
                    data += c
            except:
                break
        print("received", data)
        return data.decode("ascii").strip()
    else:
        return None

def remote_query(s, cmd):
#    if cmd.strip().lower() != "*rst" and query(s, "SOUR:PDEL:NVPR?") != "1":
#        if query(s, "SOUR:PDEL:NVPR?") != "1":          # check again
#            raise IOError("No suitable Model 2182A with the correct firmware revision is properly connected to the RS-232 port")
    msg = "SYST:COMM:SER:SEND \"" + cmd.strip() + "\""
    query(s, msg, remote=True)
    ret_msg = ""
    if cmd.split()[0].endswith("?"):
        data = query(s, "SYST:COMM:SER:ENT?", remote=True)
        n = 0
        while len(data) == 0 and n < 42:
            time.sleep(DELAY)
            data = query(s, "SYST:COMM:SER:ENT?", remote=True)
            n += 1
        ret_msg += data.strip()
        print("data len =", len(data), "cmd =", cmd)
        while len(data) == BUFFER_SIZE - 2:
            data = query(s, "SYST:COMM:SER:ENT?", remote=True)
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
s.settimeout(4)

###############
###############
###############

def ramp(x_offset, period = None, length = None):
    if period is None:
        period = COUNT
    if length is None:
        length = period
    amplitude = CURR_HIGH - CURR_LOW
    y_offset = CURR_LOW
    return [(amplitude * ((i + x_offset) - int((i + x_offset) / period) * period) / period + y_offset) for i in range(round(length))]

def trim(a, eps):
    n = 1
    while n < len(a) and abs(a[n] - a[0]) < eps:
        n += 1
    m = len(a) - 1
    while m > n and abs(a[m] - a[-1]) < eps:
        m -= 1
    return a[n:m]

def measure(s):
    query(s, "*RST")                                    # Restores 6221 defaults.
    remote_query(s, "*RST")                             # Restores 2182A defaults.

    cmds_rem_start = [
        "VOLT:RANG " + repr(COMPLIANCE),
#        "VOLT:NPLC " + repr(POWER_LINE_FREQUENCY * APER),# Specifies integration rate in PLCs: 0.01 to POWER_LINE_FREQUENCY.
        "VOLT:APER " + repr(APER),                      # Specifies integration rate in seconds: (0.01 / POWER_LINE_FREQUENCY) to 1.
        "TRAC:CLE",                                     # Clears buffer of readings.
        "TRAC:POIN " + repr(int(TOTAL_COUNT)),          # Specifies size of buffer; 2 to 1024.
#        "TRAC:FEED SENS",                              # Selects source of readings for buffer; SENSe[1], CALCulate[1], or NONE.
#        "TRAC:FEED:CONT NEV",                          # Selects buffer control mode; NEXT or NEVer.
#        "SAMP:COUN " + repr(int(TOTAL_COUNT)), 
#        "TRIG:COUN 1",
#        "TRIG:COUN " + repr(int(TOTAL_COUNT)),          # Sets measure count; 1 to 9999 or INF.
#        "TRIG:DEL:AUTO OFF",
#        "TRIG:DEL " + repr(0.0 / (WAVE_FREQ * COUNT)),  # Sets delay.
#        "TRIG:TIM " + repr(1 / (WAVE_FREQ * COUNT)),  # Sets timer interval.
#        "TRIG:SOUR TIM",
    ]
    for cmd in cmds_rem_start:
        print(cmd)
        remote_query(s, cmd)
#        time.sleep(1)

    cmds_start = [
#        "*CLS",
#        "STAT:QUE?",
#        "*ESR 0",
        "SOUR:CURR:COMP " + repr(COMPLIANCE),           # Sets compliance to COMPLIANCE.
        "SOUR:WAVE:FUNC RAMP",                          # Selects ramp wave.
        "SOUR:WAVE:FREQ " + repr(WAVE_FREQ),            # Sets frequency to WAVE_FREQ.
        "SOUR:WAVE:AMPL " + repr(CURR_HIGH),            # Sets amplitude to CURR_HIGH.
        "SOUR:WAVE:OFFS " + repr(CURR_HIGH + CURR_LOW), # Sets offset to (CURR_HIGH + CURR_LOW).
        "SOUR:WAVE:DCYC " + repr(WAVE_DCYC),            # Sets duty cycle to WAVE_DCYC%.
#        "SOUR:WAVE:EXTR " + ("ON" if PM else "OFF"),    # Enables or disables mode to externally trigger the waveform generator.
#        "SOUR:WAVE:EXTR:ILIN 1",                        # Uses line 1 for phase marker.
        "SOUR:WAVE:EXTR:IVAL -1",                       # Sets inactive value to output before/after waveform, from -1 to +1.
        "SOUR:WAVE:DUR:TIME " + repr(DURATION),         # DURATION s duration.
        "SOUR:WAVE:RANG BEST",                          # Selects best fixed source range.
#        "SOUR:WAVE:PMAR:LEV 0",                      #
#        "SOUR:WAVE:PMAR:OLINE 2",                      #
#       "SOUR:WAVE:PMAR:STAT ON",                      # Turns on phase marker.
#        "FORM:SREG BIN",                                # Selects binary format to read registers.
    ]
    for cmd in cmds_start:
        query(s, cmd)
#        time.sleep(1)

    query(s, "SOUR:WAVE:ARM")                           # Arms waveform.
    while not query(s, "SOUR:WAVE:ARM?") == "1":
        time.sleep(0.1)
    remote_query(s, "TRAC:FEED:CONT NEXT")
    remote_query(s, "INIT:CONT ON")
#    remote_query(s, "INIT:IMM")
    time.sleep(DELAY)
    print("waveform is armed")
    query(s, "SOUR:WAVE:INIT")                          # Turns on output, triggers waveform.
    print("waveform is on")
    print("waiting")
    time.sleep(DURATION)
    print("no more")
    remote_query(s, "ABOR")
#    time.sleep(DELAY)
#    query(s, "SOUR:WAVE:ABOR")                          # Stops generating waveform.

    data_u = remote_query(s, "TRAC:DATA?").split(';')[-1].split(',')

    time.sleep(1)
    print("garbage:", remote_query(s, "*OPC?")[:-1])      # clear buffer
    
    return data_u

print("ready to start")
sc = []
v = []
for t in range(REPETITIONS):
    print("ROUND %d" % t)
    m = measure(s)
    try:
        data_u = [float(u) for u in m]
#        print(len(data_u))
        for u in data_u:
            if u < -2. * COMPLIANCE or u > 2. * COMPLIANCE:
                raise "extreme voltage value: %f" % u
    except:
        print("an error occured while processing", m)
    else:
        data_u = trim(data_u[:], 0.01)
        v += data_u[:]
    
        if len(data_u) > 2:
            fft = [abs(f) for f in np.fft.rfft(data_u)]
            uppp = len(data_u) / fft.index(max(fft[1:])) + 1            # voltage points per period
        #                                                ↑↑↑ ← wtf???
        
            corr = [np.correlate(data_u, ramp(i, period = uppp))[0] for i in range(int(uppp))]
            max_corr = max(corr)
            max_corr_i = corr.index(max_corr)
            
#            plt.subplot(3, 1, 1)
#            plt.plot(data_u)
#            plt.subplot(3, 1, 2)
            data_i = ramp(max_corr_i, period = uppp, length = len(data_u))
#            plt.plot(data_i)
        #    plt.plot(fft[1:])
            
            # plt.plot(ramp(max_corr_i), data_u)
            
#            n = 0
#            for u, i in zip(data_u, data_i):
#                n += 1
#                print(n, '\t', u, '\t', i)
           
            th = False   
            th_i = None
            n = 1
            while n < min(len(data_u), len(data_i)):
                u = data_u[n]
                i = data_i[n]
                if u > THRES_U and data_u[n-1] < THRES_U:
                    if (not th) and (th_i is None or n - th_i > uppp / 2):
                        sc.append(i - (i - data_i[n-1]) / (u - data_u[n-1]) * (u - THRES_U))
                        th_i = n
                        n += int(uppp / 2)
                        th = True
                else:
                    if th:
                        th = False
                n += 1
        else:
            print("too few data points:", data_u)
#    if t < REPETITIONS - 1:
#        time.sleep(8)

if len(sc) > 1:
    # h = np.histogram(sc)
    
#    plt.subplot(3, 1, 3)
    plt.hist(sc, bins=20)
    
    fn = 'plot.png'
    plt.savefig(fn)
    
    np.savetxt('voltage.csv', v)
    np.savetxt('sc.csv', sc)

    subprocess.call(['cacaview', fn])

s.close()
print("connection closed")
    
print("done")

