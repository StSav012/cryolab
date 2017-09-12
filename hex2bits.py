import sys

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

if len(sys.argv) > 1:
    print(hex2bits(sys.argv[1]))
else:
    print("usage:\n    %s hex_string" % sys.argv[0])
    sys.exit(0)

