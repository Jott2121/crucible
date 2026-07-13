import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid, EIClass, EIData, EMachine


def test_invalid_magic_with_high_bit_byte_raises_elfinvalid_with_correct_message():
    """
    The first ident byte is 0x80 (128), which has the high bit set.
    If the ident bytes are read as *unsigned* chars (the correct
    behavior), this value stays 128 and `bytes(ident[:4])` succeeds,
    producing a mismatched-but-valid magic value that triggers a
    clean ``ELFInvalid`` with a predictable message.

    If instead the ident bytes were read as *signed* chars (mutant),
    128 would become -128, and `bytes((-128, 69, 76, 70))` would raise
    an uncaught ``ValueError`` instead of the expected ``ELFInvalid``.
    """
    data = bytes([0x80, 0x45, 0x4C, 0x46] + [0] * 12)
    f = io.BytesIO(data)

    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(f)

    expected_magic = bytes([0x80, 0x45, 0x4C, 0x46])
    assert str(exc_info.value) == f"invalid magic: {expected_magic!r}"


def test_valid_32bit_lsb_header_parses_expected_fields():
    """
    Sanity check that a well-formed 32-bit little-endian ELF header is
    parsed correctly: correct magic (0x7f 'E' 'L' 'F'), capacity,
    encoding, and machine fields.
    """
    ident = bytes(
        [0x7F, 0x45, 0x4C, 0x46, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    )
    assert len(ident) == 16

    header = struct.pack(
        "<HHIIIIIHHH",
        2,  # e_type
        EMachine.I386,  # e_machine
        1,  # e_version
        0,  # e_entry
        0,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        52,  # e_ehsize
        0,  # e_phentsize
        0,  # e_phnum
    )

    f = io.BytesIO(ident + header)
    elf = ELFFile(f)

    assert elf.capacity == EIClass.C32
    assert elf.encoding == EIData.Lsb
    assert elf.machine == EMachine.I386
