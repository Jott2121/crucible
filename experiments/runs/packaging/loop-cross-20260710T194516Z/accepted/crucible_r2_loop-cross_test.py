import io
import struct

import pytest

from packaging._elffile import ELFFile


class SparseReader:
    """A seekable reader with one payload stored at a deliberately high offset."""

    def __init__(self, prefix, payload_offset, payload):
        self.prefix = bytes(prefix)
        self.payload_offset = payload_offset
        self.payload = payload
        self.position = 0

    def read(self, size=-1):
        if self.position == self.payload_offset:
            result = self.payload if size < 0 else self.payload[:size]
            self.position += len(result)
            return result

        if size < 0:
            result = self.prefix[self.position :]
        else:
            result = self.prefix[self.position : self.position + size]
        self.position += len(result)
        return result

    def seek(self, position, whence=0):
        assert whence == 0
        self.position = position
        return position


def make_elf(capacity, encoding, *, high_offset=False):
    endian = "<" if encoding == 1 else ">"
    payload = b"/expected/interpreter\x00"

    if capacity == 1:
        e_fmt = f"{endian}HHIIIIIHHH"
        p_fmt = f"{endian}IIIIIIII"
        phentsize = struct.calcsize(p_fmt)
        payload_offset = 0x80000010 if high_offset else 160
        program_header = (
            3,  # PT_INTERP
            payload_offset,
            0x11111111,  # deliberately not an interpreter offset
            0,
            len(payload),
            1,  # deliberately not the interpreter size
            0,
            0,
        )
    else:
        e_fmt = f"{endian}HHIQQQIHHH"
        p_fmt = f"{endian}IIQQQQQQ"
        phentsize = struct.calcsize(p_fmt)
        payload_offset = (1 << 63) + 16 if high_offset else 200
        program_header = (
            3,  # PT_INTERP
            0,  # flags; deliberately not PT_INTERP
            payload_offset,
            0x1111111111111111,  # deliberately not an interpreter offset
            0,
            len(payload),
            1,  # deliberately not the interpreter size
            0,
        )

    phoff = 64
    prefix_size = phoff + phentsize if high_offset else payload_offset + len(payload)
    data = bytearray(prefix_size)
    data[:16] = b"\x7fELF" + bytes((capacity, encoding)) + b"\0" * 10

    struct.pack_into(
        e_fmt,
        data,
        16,
        2,
        3,
        1,
        0,
        phoff,
        0,
        0,
        struct.calcsize(e_fmt) + 16,
        phentsize,
        1,
    )
    struct.pack_into(p_fmt, data, phoff, *program_header)

    if high_offset:
        return SparseReader(data, payload_offset, payload)

    data[payload_offset : payload_offset + len(payload)] = payload
    return io.BytesIO(data)


@pytest.mark.parametrize(
    ("capacity", "encoding"),
    [
        (1, 1),  # 32-bit little-endian
        (1, 2),  # 32-bit big-endian
        (2, 1),  # 64-bit little-endian
        (2, 2),  # 64-bit big-endian
    ],
)
def test_interpreter_uses_correct_program_header_layout(capacity, encoding):
    elf = ELFFile(make_elf(capacity, encoding))

    assert elf.interpreter == "/expected/interpreter"


@pytest.mark.parametrize(
    ("capacity", "encoding"),
    [
        (1, 1),
        (1, 2),
        (2, 1),
        (2, 2),
    ],
)
def test_interpreter_accepts_unsigned_high_program_header_offsets(capacity, encoding):
    elf = ELFFile(make_elf(capacity, encoding, high_offset=True))

    assert elf.interpreter == "/expected/interpreter"
