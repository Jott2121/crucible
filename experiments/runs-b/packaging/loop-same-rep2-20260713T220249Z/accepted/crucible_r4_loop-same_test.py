import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


def _build_32bit_lsb_elf(machine: int, flags: int) -> bytes:
    """Construct a minimal valid 32-bit LSB ELF header (no program headers)."""
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, 1, 1]) + bytes(10)  # magic + capacity + encoding + pad
    e_type = 2
    e_version = 1
    e_entry = 0
    e_phoff = 0
    e_shoff = 0
    e_ehsize = 52
    e_phentsize = 0
    e_phnum = 0
    header = struct.pack(
        "<HHIIIIIHHH",
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


def test_valid_elf_magic_parses_correctly():
    data = _build_32bit_lsb_elf(machine=3, flags=0x12345678)
    elf = ELFFile(io.BytesIO(data))
    assert elf.capacity == 1
    assert elf.encoding == 1
    assert elf.machine == 3
    assert elf.flags == 0x12345678


def test_invalid_magic_raises_elfinvalid():
    # Wrong magic bytes (does not start with 0x7f 'E' 'L' 'F').
    bad_ident = bytes([0x00, 0x45, 0x4C, 0x46, 1, 1]) + bytes(10)
    # Pad remaining bytes so struct.unpack for the identification succeeds
    # (16 bytes total for ident, plus enough bytes so read doesn't blow up
    # before the magic check -- but the magic check happens right after
    # reading ident, so we only need 16 bytes here).
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(bad_ident))
    assert "invalid magic" in str(excinfo.value)


def test_correct_magic_value_bytes():
    # Directly verify the exact magic byte sequence expected by ELFFile,
    # ensuring the leading byte is 0x7f (127), matching b"\x7fELF".
    data = _build_32bit_lsb_elf(machine=62, flags=0)
    # Sanity: first four bytes of our constructed data are the ELF magic.
    assert data[:4] == b"\x7fELF"
    assert data[0] == 0x7F
    elf = ELFFile(io.BytesIO(data))
    assert elf.machine == 62
