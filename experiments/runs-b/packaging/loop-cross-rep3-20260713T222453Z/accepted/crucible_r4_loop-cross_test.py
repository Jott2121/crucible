import io
import struct

from packaging._elffile import ELFFile


def test_accepts_valid_elf_magic_number():
    ident = b"\x7fELF" + bytes([2, 1]) + b"\0" * 10
    header = struct.pack(
        "<HHIQQQIHHH",
        2,
        62,
        1,
        0,
        0,
        0,
        0,
        64,
        56,
        0,
    )

    elf = ELFFile(io.BytesIO(ident + header))

    assert elf.capacity == 2
    assert elf.encoding == 1
    assert elf.machine == 62
