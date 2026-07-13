import io
import struct

from packaging._elffile import ELFFile


def test_accepts_standard_elf_magic_number():
    ident = b"\x7fELF" + bytes([1, 1]) + b"\0" * 10
    header = struct.pack(
        "<HHIIIIIHHH",
        2,
        3,
        1,
        0,
        0,
        0,
        0,
        52,
        32,
        0,
    )

    elf = ELFFile(io.BytesIO(ident + header))

    assert elf.capacity == 1
    assert elf.encoding == 1
    assert elf.machine == 3
