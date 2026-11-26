"""IMA ADPCM decompression as used in MPQ archives (WAVE files).

Port of StormLib's adpcm.cpp (MIT licence, (c) Ladislav Zezula).
"""
import struct

_NEXT_STEP = [
    -1, 0, -1, 4, -1, 2, -1, 6,
    -1, 1, -1, 5, -1, 3, -1, 7,
    -1, 1, -1, 5, -1, 3, -1, 7,
    -1, 2, -1, 4, -1, 6, -1, 8,
]

_STEP_SIZE = [
    7, 8, 9, 10, 11, 12, 13, 14,
    16, 17, 19, 21, 23, 25, 28, 31,
    34, 37, 41, 45, 50, 55, 60, 66,
    73, 80, 88, 97, 107, 118, 130, 143,
    157, 173, 190, 209, 230, 253, 279, 307,
    337, 371, 408, 449, 494, 544, 598, 658,
    724, 796, 876, 963, 1060, 1166, 1282, 1411,
    1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024,
    3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484,
    7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794,
    32767,
]

INITIAL_STEP_INDEX = 0x2C


def decompress_adpcm(data: bytes, channels: int, out_length: int | None = None) -> bytes:
    if len(data) < 2:
        return b""
    bit_shift = data[1]
    pos = 2
    predicted = [0, 0]
    step_index = [INITIAL_STEP_INDEX, INITIAL_STEP_INDEX]
    samples = []
    max_samples = (out_length // 2) if out_length is not None else None

    for ch in range(channels):
        if pos + 2 > len(data):
            return struct.pack(f"<{len(samples)}h", *samples)
        (s,) = struct.unpack_from("<h", data, pos)
        pos += 2
        predicted[ch] = s
        samples.append(s)

    ch = channels - 1
    n = len(data)
    while pos < n:
        if max_samples is not None and len(samples) >= max_samples:
            break
        enc = data[pos]
        pos += 1
        ch = (ch + 1) % channels
        if enc == 0x80:
            if step_index[ch] != 0:
                step_index[ch] -= 1
            samples.append(predicted[ch])
        elif enc == 0x81:
            step_index[ch] += 8
            if step_index[ch] > 0x58:
                step_index[ch] = 0x58
            ch = (ch + 1) % channels
        else:
            si = step_index[ch]
            step = _STEP_SIZE[si]
            diff = step >> bit_shift
            if enc & 0x01: diff += step
            if enc & 0x02: diff += step >> 1
            if enc & 0x04: diff += step >> 2
            if enc & 0x08: diff += step >> 3
            if enc & 0x10: diff += step >> 4
            if enc & 0x20: diff += step >> 5
            p = predicted[ch]
            if enc & 0x40:
                p -= diff
                if p <= -32768:
                    p = -32768
            else:
                p += diff
                if p >= 32767:
                    p = 32767
            predicted[ch] = p
            samples.append(p)
            si += _NEXT_STEP[enc & 0x1F]
            step_index[ch] = 0 if si < 0 else (88 if si > 88 else si)
    if max_samples is not None:
        samples = samples[:max_samples]
    return struct.pack(f"<{len(samples)}h", *samples)
