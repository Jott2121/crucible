import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


def _make_ident(capacity: int, encoding: int) -> bytes:
    # 16-byte ELF identification block:
    # magic(4) + capacity(1) + encoding(1) + version(1) + 9 padding bytes
    return b"\x7fELF" + bytes([capacity, encoding, 1]) + b"\x00" * 9


def test_elf_machine_field_32bit_lsb_unsigned():
    # Regression test for mutant that changes "<HHIIIIIHHH" to "<hhiiiiihhh"
    # (unsigned -> signed) for the 32-bit LSB e_fmt. Using a machine value
    # with the high bit set (32769) distinguishes signed vs unsigned parsing.
    ident = _make_ident(capacity=1, encoding=1)
    machine_value = 32769  # > 0x7FFF, so signed vs unsigned differ.
    header = struct.pack(
        "<HHIIIIIHHH",
        0,  # e_type
        machine_value,  # e_machine
        0,  # e_version
        0,  # e_entry
        0,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        0,  # e_ehsize
        0,  # e_phentsize
        0,  # e_phnum
    )
    data = ident + header
    elf = ELFFile(io.BytesIO(data))
    assert elf.machine == machine_value


def test_elf_machine_field_32bit_msb_unsigned():
    # Regression test for mutant that changes ">HHIIIIIHHH" to ">hhiiiiihhh"
    # (unsigned -> signed) for the 32-bit MSB e_fmt.
    ident = _make_ident(capacity=1, encoding=2)
    machine_value = 32769  # > 0x7FFF, so signed vs unsigned differ.
    header = struct.pack(
        ">HHIIIIIHHH",
        0,  # e_type
        machine_value,  # e_machine
        0,  # e_version
        0,  # e_entry
        0,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        0,  # e_ehsize
        0,  # e_phentsize
        0,  # e_phnum
    )
    data = ident + header
    elf = ELFFile(io.BytesIO(data))
    assert elf.machine == machine_value


def test_elf_invalid_capacity_reported_as_unsigned():
    # Regression test for mutant that changes self._read("16B") to
    # self._read("16b") (unsigned -> signed byte parsing of the ident
    # block). A capacity byte of 255 should be reported as 255 (unsigned),
    # not -1 (signed), in the resulting error message.
    ident = _make_ident(capacity=255, encoding=1)
    # No further bytes are needed since parsing fails while decoding ident
    # capacity/encoding lookup, but ELFFile still needs the e_fmt struct
    # size available conceptually; however since KeyError happens before
    # reading e_fmt, we don't need to supply it.
    data = ident
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(data))
    assert "255" in str(exc_info.value)
