import io
import struct

import pytest

from packaging._elffile import EIClass, EIData, ELFFile, ELFInvalid, EMachine


def _pack_ident(capacity: int, encoding: int) -> bytes:
    return b"\x7fELF" + bytes([capacity, encoding]) + bytes(10)


def _build_32_lsb_with_interp() -> bytes:
    ident = _pack_ident(1, 1)  # 32-bit, LSB
    e_fmt = "<HHIIIIIHHH"
    p_fmt = "<IIIIIIII"

    elf_header_size = struct.calcsize(e_fmt)
    p_entsize = struct.calcsize(p_fmt)

    ident_and_header_size = len(ident) + elf_header_size
    phoff = ident_and_header_size
    interp_offset = phoff + p_entsize

    interp_bytes = b"/lib/ld.so\x00"

    elf_header = struct.pack(
        e_fmt,
        2,      # e_type
        62,     # e_machine -> X8664
        1,      # e_version
        0,      # e_entry
        phoff,  # e_phoff
        0,      # e_shoff
        999,    # e_flags
        52,     # e_ehsize
        p_entsize,  # e_phentsize
        1,      # e_phnum
    )

    program_header = struct.pack(
        p_fmt,
        3,              # p_type -> PT_INTERP
        interp_offset,  # p_offset
        0,              # p_vaddr
        0,              # p_paddr
        len(interp_bytes),  # p_filesz
        0,              # p_memsz
        0,              # p_flags
        0,              # p_align
    )

    return ident + elf_header + program_header + interp_bytes


def _build_64_msb_no_interp() -> bytes:
    ident = _pack_ident(2, 2)  # 64-bit, MSB
    e_fmt = ">HHIQQQIHHH"

    elf_header = struct.pack(
        e_fmt,
        2,      # e_type
        183,    # e_machine -> AArch64
        1,      # e_version
        0,      # e_entry
        0,      # e_phoff
        0,      # e_shoff
        0,      # e_flags
        64,     # e_ehsize
        0,      # e_phentsize
        0,      # e_phnum
    )

    return ident + elf_header


def test_eiclass_values():
    assert EIClass.C32 == 1
    assert EIClass.C64 == 2


def test_eidata_values():
    assert EIData.Lsb == 1
    assert EIData.Msb == 2


def test_emachine_values():
    assert EMachine.I386 == 3
    assert EMachine.S390 == 22
    assert EMachine.Arm == 40
    assert EMachine.X8664 == 62
    assert EMachine.AArch64 == 183


def test_elfinvalid_is_value_error():
    assert issubclass(ELFInvalid, ValueError)


def test_32bit_lsb_with_interpreter():
    data = _build_32_lsb_with_interp()
    elf = ELFFile(io.BytesIO(data))

    assert elf.capacity == 1
    assert elf.encoding == 1
    assert elf.machine == EMachine.X8664
    assert elf.flags == 999
    assert elf.interpreter == "/lib/ld.so"


def test_64bit_msb_no_program_headers():
    data = _build_64_msb_no_interp()
    elf = ELFFile(io.BytesIO(data))

    assert elf.capacity == 2
    assert elf.encoding == 2
    assert elf.machine == EMachine.AArch64
    assert elf.flags == 0
    assert elf.interpreter is None


def test_invalid_magic_raises():
    bad_ident = b"ABCD" + bytes([1, 1]) + bytes(10)
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(bad_ident))


def test_truncated_ident_raises():
    too_short = b"\x7fELF\x01\x01"  # only 6 bytes, not enough for 16B ident
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(too_short))


def test_unrecognized_capacity_encoding_raises():
    ident = _pack_ident(3, 1)  # capacity=3 is not a recognized value
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(ident))


def test_unrecognized_encoding_raises():
    ident = _pack_ident(1, 3)  # encoding=3 is not a recognized value
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(ident))


def test_truncated_after_ident_raises_on_header_parse():
    # Valid ident/capacity/encoding but not enough bytes for the ELF header.
    ident = _pack_ident(1, 1)
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(ident))
