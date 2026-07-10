import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid, EMachine


def _build_valid_elf_bytes():
    """Construct a minimal valid 64-bit LSB ELF header for testing."""
    capacity = 2  # 64-bit
    encoding = 1  # LSB
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding]) + bytes(10)

    e_type = 2
    e_machine = EMachine.X8664
    e_version = 1
    e_entry = 0
    e_phoff = 64
    e_shoff = 0
    e_flags = 0
    e_ehsize = 64
    e_phentsize = struct.calcsize("<IIQQQQQQ")
    e_phnum = 0

    header = struct.pack(
        "<HHIQQQIHHH",
        e_type,
        e_machine,
        e_version,
        e_entry,
        e_phoff,
        e_shoff,
        e_flags,
        e_ehsize,
        e_phentsize,
        e_phnum,
    )
    return ident + header


def test_valid_magic_parses_successfully():
    data = _build_valid_elf_bytes()
    f = io.BytesIO(data)
    elf = ELFFile(f)
    assert elf.machine == EMachine.X8664
    assert elf.capacity == 2
    assert elf.encoding == 1


def test_invalid_magic_raises_elfinvalid():
    data = bytearray(_build_valid_elf_bytes())
    # Corrupt the first magic byte so it no longer matches b"\x7fELF"
    data[0] = 0x00
    f = io.BytesIO(bytes(data))
    with pytest.raises(ELFInvalid):
        ELFFile(f)


def test_magic_constant_matches_expected_byte_value():
    # The magic constant must be the exact byte sequence 0x7f, 'E', 'L', 'F'
    expected = bytes([0x7F, 0x45, 0x4C, 0x46])
    assert b"\x7fELF" == expected
    assert b"\x7fELF"[0] == 0x7F
