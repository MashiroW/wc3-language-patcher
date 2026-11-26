"""PKWARE Data Compression Library "explode" (decompression).

Port of Mark Adler's blast.c (zlib contrib, public domain-like zlib licence).
"""

MAXBITS = 13

_LITLEN = bytes([
    11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8,
    9, 7, 6, 7, 8, 7, 6, 55, 8, 23, 24, 12, 11, 7, 9, 11, 12, 6, 7, 22, 5,
    7, 24, 6, 11, 9, 6, 7, 22, 7, 11, 38, 7, 9, 8, 25, 11, 8, 11, 9, 12,
    8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10, 53, 8, 7, 24, 10, 27,
    44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45,
    44, 173])
_LENLEN = bytes([2, 35, 36, 53, 38, 23])
_DISTLEN = bytes([2, 20, 53, 230, 247, 151, 248])
_BASE = [3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264]
_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8]


class ExplodeError(Exception):
    pass


def _construct(rep, n):
    lengths = []
    for b in rep:
        length = b & 15
        count = (b >> 4) + 1
        lengths.extend([length] * count)
    lengths = lengths[:n]
    count = [0] * (MAXBITS + 1)
    for length in lengths:
        count[length] += 1
    offs = [0] * (MAXBITS + 2)
    for length in range(1, MAXBITS + 1):
        offs[length + 1] = offs[length] + count[length]
    symbol = [0] * n
    for sym, length in enumerate(lengths):
        if length:
            symbol[offs[length]] = sym
            offs[length] += 1
    return count, symbol


_LITCODE = _construct(_LITLEN, 256)
_LENCODE = _construct(_LENLEN, 16)
_DISTCODE = _construct(_DISTLEN, 64)


class _Bits:
    __slots__ = ("data", "pos", "buf", "cnt")

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.buf = 0
        self.cnt = 0

    def bits(self, need):
        val = self.buf
        while self.cnt < need:
            if self.pos >= len(self.data):
                raise ExplodeError("input exhausted")
            val |= self.data[self.pos] << self.cnt
            self.pos += 1
            self.cnt += 8
        self.buf = val >> need
        self.cnt -= need
        return val & ((1 << need) - 1)

    def decode(self, h):
        count, symbol = h
        code = first = index = 0
        for length in range(1, MAXBITS + 1):
            code |= self.bits(1) ^ 1  # codes are stored inverted
            c = count[length]
            if code < first + c:
                return symbol[index + (code - first)]
            index += c
            first += c
            first <<= 1
            code <<= 1
        raise ExplodeError("ran out of codes")


def explode(data: bytes, expected_size: int | None = None) -> bytes:
    s = _Bits(data)
    lit = s.bits(8)
    if lit > 1:
        raise ExplodeError("bad literal flag")
    dictbits = s.bits(8)
    if dictbits < 4 or dictbits > 6:
        raise ExplodeError("bad dictionary size")
    out = bytearray()
    while True:
        if expected_size is not None and len(out) >= expected_size:
            break
        if s.bits(1):
            symbol = s.decode(_LENCODE)
            length = _BASE[symbol] + s.bits(_EXTRA[symbol])
            if length == 519:
                break
            sym = 2 if length == 2 else dictbits
            dist = (s.decode(_DISTCODE) << sym) + s.bits(sym) + 1
            if dist > len(out):
                raise ExplodeError("distance too far back")
            start = len(out) - dist
            for k in range(length):
                out.append(out[start + k])
        else:
            out.append(s.decode(_LITCODE) if lit else s.bits(8))
    return bytes(out)
