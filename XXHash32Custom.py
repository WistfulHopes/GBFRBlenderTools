import struct

"""
Utility class for custom XXHash32 hashing.
Original custom XXHash32 reverse engineering by: Nenkai
https://github.com/Nenkai/GBFRDataTools/blob/master/GBFRDataTools.Hashing/XXHash32Custom.cs

Notes:
    Python Implementation requires & 0xFFFFFFFF after every arithmetic step to ensure 32-bit uint range.
"""

PRIME32_1 = 0x9E3779B1
PRIME32_2 = 0x85EBCA77
PRIME32_3 = 0xC2B2AE3D
PRIME32_4 = 0x27D4EB2F
PRIME32_5 = 0x165667B1

@staticmethod
def _XXH32_rotl(x, r):
    return ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF

@staticmethod
def _XXH32_round(seed, input):
    return (_XXH32_rotl((seed + input * PRIME32_2) & 0xFFFFFFFF, 13) * PRIME32_1) & 0xFFFFFFFF

@staticmethod
def Hash_string(string:str) -> int:
    """
    XXHash32 a string.
    """
    return Hash_bytes(string.encode('ascii'))

@staticmethod
def Hash_bytes(input:bytes) -> int:
    """
    XXHash32 a buffer.
    """
    h32 = 0x178A54A4 # This is different
    p = 0

    if len(input) >= 16:
        """Orig
        var v1 = h32 + PRIME32_1 + PRIME32_2;
        var v2 = h32 + PRIME32_2;
        var v3 = h32 + 0;
        var v4 = h32 - PRIME32_1;
        """

        """
        No idea how these are calculated but this is also different
        var v1 = 0x2557311B;
        var v2 = 0x871FB76A;
        var v3 = 0x0133ECF3;
        var v4 = 0x62FC7342;
        """
        v1 = 0x2557311B
        v2 = 0x871FB76A
        v3 = 0x0133ECF3
        v4 = 0x62FC7342

        limit = len(input) - 16
        while p <= limit:
            v1 = _XXH32_round(v1, struct.unpack_from('<I', input, p)[0])
            v2 = _XXH32_round(v2, struct.unpack_from('<I', input, p + 4)[0])
            v3 = _XXH32_round(v3, struct.unpack_from('<I', input, p + 8)[0])
            v4 = _XXH32_round(v4, struct.unpack_from('<I', input, p + 12)[0])
            p += 16

        h32 = (_XXH32_rotl(v1, 1) + _XXH32_rotl(v2, 7) + _XXH32_rotl(v3, 12) + _XXH32_rotl(v4, 18)) & 0xFFFFFFFF

    h32 = (h32 + len(input)) & 0xFFFFFFFF

    while p + 4 <= len(input):
        k1 = struct.unpack_from('<I', input, p)[0]
        h32 = (_XXH32_rotl((h32 + k1 * PRIME32_3) & 0xFFFFFFFF, 17) * PRIME32_4) & 0xFFFFFFFF
        p += 4

    while p < len(input):
        h32 = (_XXH32_rotl((h32 + input[p] * PRIME32_5) & 0xFFFFFFFF, 11) * PRIME32_1) & 0xFFFFFFFF
        p += 1

    h32 ^= h32 >> 15
    h32 = (h32 * PRIME32_2) & 0xFFFFFFFF
    h32 ^= h32 >> 13
    h32 = (h32 * PRIME32_3) & 0xFFFFFFFF
    h32 ^= h32 >> 16

    return h32



# Get Hex
# h32.to_bytes(4, byteorder="big").hex().upper()