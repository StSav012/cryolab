import socket
import time

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

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((TCP_IP, TCP_PORT))
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

def ramp(s):
    WAVE_FREQ = 1
    WAVE_DCYC = 100
    CURR_HIGH = 1.0e-6
    CURR_LOW = 0
    PM = False
    DURATION = 2
    COUNT = 21

    query(s, "*RST")                                    # Restores 6221 defaults.
    remote_query(s, "*RST")                             # Restores 2182A defaults.

    cmds_rem_start = [
        "VOLT:RANG 10",
#        "VOLT:NPLC " + repr(POWER_LINE_FREQUENCY / WAVE_FREQ / (COUNT - 1) / 5),# Specifies integration rate in PLCs: 0.01 to POWER_LINE_FREQUENCY.
        "VOLT:APER " + repr(0.2 / WAVE_FREQ / (COUNT - 1)), # Specifies integration rate in seconds: (0.01 / POWER_LINE_FREQUENCY) to 1.
        "TRAC:CLE",                                     # Clears buffer of readings.
        "TRAC:POIN " + repr(int(DURATION * WAVE_FREQ * COUNT)), # Specifies size of buffer; 2 to 1024.
#        "TRAC:FEED SENS",                               # Selects source of readings for buffer; SENSe[1], CALCulate[1], or NONE.
#        "TRAC:FEED:CONT NEV",                          # Selects buffer control mode; NEXT or NEVer.
#        "TRIG:COUN " + repr(1),                         # Sets measure count; 1 to 9999 or INF.
#        "TRIG:DEL 0",                                   # Sets no delay.
#        "TRIG:DEL:AUTO OFF",
        "TRIG:TIM " + repr(1 / WAVE_FREQ / (COUNT - 1)),  # Sets timer interval.
        "TRIG:SOUR TIM",
    ]
    for cmd in cmds_rem_start:
        print(cmd)
        remote_query(s, cmd)

    cmds_start = [
        "SOUR:CURR:COMP 1",                             # Sets compliance to 1V.
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

    query(s, "SOUR:WAVE:ARM")                           # Arms waveform.
    while not query(s, "SOUR:WAVE:ARM?") == "1":
        time.sleep(0.1)
    remote_query(s, "TRAC:FEED:CONT NEXT")
    remote_query(s, "INIT:CONT ON")
    time.sleep(0.82)
#    remote_query(s, "INIT:IMM")
    query(s, "SOUR:WAVE:INIT")                          # Turns on output, trigger waveform.
#    data_u = []
#    for n in range(DURATION * WAVE_FREQ * COUNT):
#        query(s, "*TRG")
#        data_u.append(remote_query(s, "FETC?"))
#        time.sleep(1.0 / WAVE_FREQ / COUNT)
    time.sleep(DURATION)
    remote_query(s, "ABOR")
    query(s, "SOUR:WAVE:ABOR")                          # Stops generating waveform.
#    while not remote_query(s, "*OPC?") == "1":
#        time.sleep(0.1)

#    print(remote_query(s, "TRAC:POIN?"))
#    print(remote_query(s, "READ?"))
#    print(remote_query(s, "TRAC:DATA?"))
    data_u = remote_query(s, "TRAC:DATA?").split(',')
#    print(data_u)
    n = 0
    for u in data_u:
        i = None
        if len(u) > 0:
            i = float(u) / 0.39e6 # CURR_LOW + (CURR_HIGH - CURR_LOW) / (COUNT - 1) * (n % COUNT)
        else:
            i = ""
        n += 1
        print(n, '\t', i, '\t', u)

    time.sleep(1)
    print("garbage:", remote_query(s, "*OPC?"))      # clear buffer


#iv_curve(s, 3)
ramp(s)

s.close()

