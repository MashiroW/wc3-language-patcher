"""Adaptive Huffman decompression used by MPQ archives (mostly for WAVE files).

Port of StormLib's huff.cpp (MIT licence, (c) Ladislav Zezula), without the
quick-link cache (which is only a speed optimisation).
Items live in parallel arrays; index 0 is the list head sentinel.
"""
from .huffman_tables import DATA_DISTRIBUTIONS

HUFF_ITEM_COUNT = 515
NIL = -1


class HuffmanError(Exception):
    pass


class _Tree:
    def __init__(self):
        n = HUFF_ITEM_COUNT + 1
        self.nxt = [0] * n
        self.prv = [0] * n
        self.weight = [0] * n
        self.value = [0] * n
        self.parent = [NIL] * n
        self.child_lo = [NIL] * n
        self.linked = [False] * n
        self.used = 1  # slot 0 = head
        self.nxt[0] = self.prv[0] = 0
        self.by_byte = [NIL] * 0x102

    # -- list helpers -------------------------------------------------------
    def remove(self, i):
        if self.linked[i]:
            p, n = self.prv[i], self.nxt[i]
            self.nxt[p] = n
            self.prv[n] = p
            self.linked[i] = False

    def link_after(self, a, b):
        """insert b right after a"""
        n = self.nxt[a]
        self.nxt[b] = n
        self.prv[b] = a
        self.prv[n] = b
        self.nxt[a] = b
        self.linked[b] = True

    def find_higher_or_equal(self, i, w):
        weight, prv = self.weight, self.prv
        while i != 0:
            if weight[i] >= w:
                return i
            i = prv[i]
        return 0

    def create(self, value, w, before_head):
        if self.used >= HUFF_ITEM_COUNT + 1:
            raise HuffmanError("tree item pool exhausted")
        i = self.used
        self.used += 1
        if before_head:          # InsertBefore(head) == append at the tail
            self.link_after(self.prv[0], i)
        else:                    # InsertAfter(head) == push at the front
            self.link_after(0, i)
        self.value[i] = value
        self.weight[i] = w
        self.parent[i] = NIL
        self.child_lo[i] = NIL
        return i

    def fixup_pos(self, i, max_weight):
        if self.weight[i] < max_weight:
            higher = self.find_higher_or_equal(self.prv[0], self.weight[i])
            self.remove(i)
            self.link_after(higher, i)
            return max_weight
        return self.weight[i]

    def build(self, data_type):
        data_type &= 0x0F
        if data_type >= len(DATA_DISTRIBUTIONS):
            raise HuffmanError(f"bad Huffman data type {data_type}")
        table = DATA_DISTRIBUTIONS[data_type]
        max_weight = 0
        for b in range(0x100):
            if table[b]:
                i = self.create(b, table[b], False)
                self.by_byte[b] = i
                max_weight = self.fixup_pos(i, max_weight)
        self.by_byte[0x100] = self.create(0x100, 1, True)
        self.by_byte[0x101] = self.create(0x101, 1, True)

        lo = self.prv[0]
        while lo != 0:
            hi = self.prv[lo]
            if hi == 0:
                break
            p = self.create(0, self.weight[hi] + self.weight[lo], False)
            self.parent[lo] = p
            self.parent[hi] = p
            self.child_lo[p] = lo
            max_weight = self.fixup_pos(p, max_weight)
            lo = self.prv[hi]

    def inc_weights(self, i):
        weight, parent, child_lo = self.weight, self.parent, self.child_lo
        while i != NIL:
            weight[i] += 1
            higher = self.find_higher_or_equal(self.prv[i], weight[i])
            hi = self.nxt[higher]
            if hi != i:
                self.remove(hi)
                self.link_after(i, hi)
                self.remove(i)
                self.link_after(higher, i)

                lo_of_hi_parent = child_lo[parent[hi]]
                p = parent[i]
                if child_lo[p] == i:
                    child_lo[p] = hi
                if lo_of_hi_parent == hi:
                    child_lo[parent[hi]] = i
                p = parent[i]
                parent[i] = parent[hi]
                parent[hi] = p
            i = parent[i]

    def insert_new_branch(self, value1, value2):
        last = self.prv[0]
        hi = self.create(value1, self.weight[last], True)
        self.parent[hi] = last
        self.by_byte[value1] = hi
        lo = self.create(value2, 0, True)
        self.parent[lo] = last
        self.child_lo[last] = lo
        self.by_byte[value2] = lo
        self.inc_weights(lo)


def decompress_huffman(data: bytes, out_length: int | None = None) -> bytes:
    pos = 0
    end = len(data)
    bitbuf = 0
    bitcnt = 0

    def get8():
        nonlocal pos, bitbuf, bitcnt
        if bitcnt < 8:
            if pos >= end:
                raise HuffmanError("input exhausted")
            bitbuf |= data[pos] << bitcnt
            pos += 1
            bitcnt += 8
        v = bitbuf & 0xFF
        bitbuf >>= 8
        bitcnt -= 8
        return v

    data_type = get8()
    sparse = data_type == 0
    t = _Tree()
    t.build(data_type)
    out = bytearray()
    child_lo, prv, value = t.child_lo, t.prv, t.value

    while True:
        # decode one symbol
        i = t.nxt[0]
        if i == 0:
            raise HuffmanError("empty tree")
        while child_lo[i] != NIL:
            if bitcnt == 0:
                if pos >= end:
                    raise HuffmanError("input exhausted")
                bitbuf = data[pos]
                pos += 1
                bitcnt = 8
            bit = bitbuf & 1
            bitbuf >>= 1
            bitcnt -= 1
            i = prv[child_lo[i]] if bit else child_lo[i]
        v = value[i]
        if v == 0x100:
            break
        if v == 0x101:
            v = get8()
            t.insert_new_branch(t.value[t.prv[0]], v)
            if not sparse:
                t.inc_weights(t.by_byte[v])
        if out_length is not None and len(out) >= out_length:
            break
        out.append(v)
        if sparse:
            t.inc_weights(t.by_byte[v])
    return bytes(out)
