import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid, EIClass, EIData, EMachine


def _build_valid_elf_bytes():
    # 16-byte e_ident: magic (0x7f 'E' 'L' 'F'), EI_CLASS=2 (64-bit),
    # EI_DATA=1 (LSB), rest padding zeros.
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    # e_fmt for (2, 1) capacity/encoding is "<HHIQQQIHHH"
    header = struct.pack(
        "<HHIQQQIHHH",
        1,  # e_type
        int(EMachine.X8664),  # e_machine
        1,  # e_version
        0,  # e_entry
        64,  # e_phoff
        0,  # e_shoff
        0xDEADBEEF & 0xFFFFFFFF,  # e_flags
        64,  # e_ehsize
        56,  # e_phentsize
        0,  # e_phnum
    )
    return ident + header


def test_valid_elf_magic_parses_correctly():
    data = _build_valid_elf_bytes()
    f = io.BytesIO(data)
    elf = ELFFile(f)

    assert elf.capacity == EIClass.C64
    assert elf.encoding == EIData.Lsb
    assert elf.machine == EMachine.X8664
    assert elf.flags == (0xDEADBEEF & 0xFFFFFFFF)


def test_invalid_magic_first_byte_raises_elfinvalid():
    data = bytearray(_build_valid_elf_bytes())
    # Corrupt the first magic byte so it no longer matches b"\x7fELF"
    data[0] = 0x00
    f = io.BytesIO(bytes(data))

    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(f)

    # The error message should include the (invalid) magic bytes actually read.
    expected_magic = bytes(data[:4])
    assert repr(expected_magic) in str(exc_info.value)


def test_correct_magic_byte_value_is_0x7f():
    # This directly pins down that byte 0x7F (0x7f) is the expected first
    # magic byte -- distinguishing it from any other value would fail parsing.
    data = bytearray(_build_valid_elf_bytes())
    assert data[0] == 0x7F

    # Using the correct magic byte, parsing succeeds without error.
    f = io.BytesIO(bytes(data))
    elf = ELFFile(f)
    assert elf.capacity == EIClass.C64
