import io
import struct

import pytest

from packaging._elffile import ELFFile


def _build_header(capacity: int, encoding: int, machine: int, flags: int) -> bytes:
    """
    Build a minimal, valid ELF identification + header (no program headers)
    for the given capacity/encoding combination, with custom machine and
    flags values so we can detect signed/unsigned interpretation differences.
    """
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding] + [0] * 10)
    endian = "<" if encoding == 1 else ">"
    if capacity == 1:
        e_fmt = endian + "HHIIIIIHHH"
    else:
        e_fmt = endian + "HHIQQQIHHH"

    e_type = 0
    e_version = 1
    e_entry = 0
    e_phoff = 0
    e_shoff = 0
    e_ehsize = 0
    e_phentsize = 0
    e_phnum = 0

    header = struct.pack(
        e_fmt,
        e_type,
        machine,
        e_version,
        e_entry,
        e_phoff,
        e_shoff,
        flags,
        e_ehsize,
        e_phentsize,
        e_phnum,
    )
    return ident + header


@pytest.mark.parametrize(
    "capacity,encoding,expected_p_fmt",
    [
        (1, 1, "<IIIIIIII"),
        (1, 2, ">IIIIIIII"),
        (2, 1, "<IIQQQQQQ"),
        (2, 2, ">IIQQQQQQ"),
    ],
)
def test_elffile_header_and_program_format_parsing(capacity, encoding, expected_p_fmt):
    # machine_value has its high bit set within a 16-bit field: if the ELF
    # header format ever used a signed short ('h') instead of the correct
    # unsigned short ('H'), this value would be read as a negative number.
    machine_value = 0x8000  # 32768

    # flags_value has its high bit set within a 32-bit field: if the ELF
    # header format ever used a signed int ('i') instead of the correct
    # unsigned int ('I'), this value would be read as a negative number.
    flags_value = 0x80000000  # 2147483648

    data = _build_header(capacity, encoding, machine_value, flags_value)
    elf = ELFFile(io.BytesIO(data))

    # Sanity: identification parsed correctly.
    assert elf.capacity == capacity
    assert elf.encoding == encoding

    # These would be negative under a mutated (signed) e_fmt.
    assert elf.machine == machine_value
    assert elf.flags == flags_value

    # The program header format string must exactly match the expected
    # unsigned layout for this capacity/encoding combination.
    assert elf._p_fmt == expected_p_fmt
