import io
import struct

import pytest

from packaging._elffile import EIClass, EIData, ELFFile, ELFInvalid, EMachine


# ---------------------------------------------------------------------------
# Enum value tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Invalid input tests
# ---------------------------------------------------------------------------


def test_invalid_magic_raises():
    # 16 bytes total, but wrong magic.
    data = b"BADM" + bytes([1, 1]) + b"\x00" * 10
    assert len(data) == 16
    f = io.BytesIO(data)
    with pytest.raises(ELFInvalid):
        ELFFile(f)


def test_too_short_identification_raises():
    # Less than 16 bytes -> struct.error internally -> ELFInvalid.
    f = io.BytesIO(b"\x7fELF")
    with pytest.raises(ELFInvalid):
        ELFFile(f)


def test_unrecognized_capacity_encoding_raises():
    # Valid magic, but capacity/encoding combo not in the lookup table.
    data = b"\x7fELF" + bytes([3, 1]) + b"\x00" * 10
    assert len(data) == 16
    f = io.BytesIO(data)
    with pytest.raises(ELFInvalid):
        ELFFile(f)


def test_truncated_header_raises():
    # Valid ident (32-bit LSB) but header data truncated.
    ident = b"\x7fELF" + bytes([1, 1]) + b"\x00" * 10
    f = io.BytesIO(ident + b"\x00\x01")  # Not enough bytes for e_fmt.
    with pytest.raises(ELFInvalid):
        ELFFile(f)


# ---------------------------------------------------------------------------
# Valid 32-bit LSB ELF, no program headers -> interpreter is None
# ---------------------------------------------------------------------------


def _build_32le_no_phdrs(machine, flags):
    ident = b"\x7fELF" + bytes([1, 1]) + b"\x00" * 10
    e_fmt = "<HHIIIIIHHH"
    header = struct.pack(
        e_fmt,
        2,  # e_type
        machine,  # e_machine
        1,  # e_version
        0,  # e_entry
        0,  # e_phoff
        0,  # e_shoff
        flags,  # e_flags
        52,  # e_ehsize
        32,  # e_phentsize
        0,  # e_phnum
    )
    return ident + header


def test_32bit_lsb_basic_attributes():
    data = _build_32le_no_phdrs(machine=3, flags=0x1234)
    f = io.BytesIO(data)
    elf = ELFFile(f)
    assert elf.capacity == EIClass.C32
    assert elf.encoding == EIData.Lsb
    assert elf.machine == EMachine.I386
    assert elf.flags == 0x1234


def test_32bit_lsb_no_program_headers_interpreter_none():
    data = _build_32le_no_phdrs(machine=3, flags=0)
    f = io.BytesIO(data)
    elf = ELFFile(f)
    assert elf.interpreter is None


# ---------------------------------------------------------------------------
# Valid 32-bit LSB ELF with a PT_INTERP program header
# ---------------------------------------------------------------------------


def test_32bit_lsb_interpreter_found():
    ident = b"\x7fELF" + bytes([1, 1]) + b"\x00" * 10
    e_fmt = "<HHIIIIIHHH"

    e_phoff = 46  # 16 (ident) + 30 (header)
    e_phentsize = 32
    e_phnum = 1

    header = struct.pack(
        e_fmt,
        2,  # e_type
        62,  # e_machine (X86-64)
        1,  # e_version
        0,  # e_entry
        e_phoff,
        0,  # e_shoff
        0,  # e_flags
        52,  # e_ehsize
        e_phentsize,
        e_phnum,
    )
    assert len(header) == 30

    interp_str = "/lib/ld-test.so"
    interp_bytes = interp_str.encode("utf-8") + b"\x00"
    p_offset = e_phoff + e_phentsize  # right after the program header

    p_fmt = "<IIIIIIII"
    phdr = struct.pack(
        p_fmt,
        3,  # p_type = PT_INTERP
        p_offset,  # p_offset
        0,  # p_vaddr
        0,  # p_paddr
        len(interp_bytes),  # p_filesz
        0,  # p_memsz
        0,  # p_flags
        0,  # p_align
    )
    assert len(phdr) == e_phentsize

    full = ident + header + phdr + interp_bytes
    f = io.BytesIO(full)
    elf = ELFFile(f)
    assert elf.interpreter == interp_str


# ---------------------------------------------------------------------------
# Valid 64-bit LSB and MSB ELF headers, no program headers
# ---------------------------------------------------------------------------


def test_64bit_lsb_basic_attributes():
    ident = b"\x7fELF" + bytes([2, 1]) + b"\x00" * 10
    e_fmt = "<HHIQQQIHHH"
    header = struct.pack(
        e_fmt,
        2,  # e_type
        183,  # e_machine (AArch64)
        1,  # e_version
        0,  # e_entry
        0,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        64,  # e_ehsize
        56,  # e_phentsize
        0,  # e_phnum
    )
    f = io.BytesIO(ident + header)
    elf = ELFFile(f)
    assert elf.capacity == EIClass.C64
    assert elf.encoding == EIData.Lsb
    assert elf.machine == EMachine.AArch64
    assert elf.interpreter is None


def test_64bit_msb_basic_attributes():
    ident = b"\x7fELF" + bytes([2, 2]) + b"\x00" * 10
    e_fmt = ">HHIQQQIHHH"
    header = struct.pack(
        e_fmt,
        2,  # e_type
        40,  # e_machine (Arm)
        1,  # e_version
        0,  # e_entry
        0,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        64,  # e_ehsize
        56,  # e_phentsize
        0,  # e_phnum
    )
    f = io.BytesIO(ident + header)
    elf = ELFFile(f)
    assert elf.capacity == EIClass.C64
    assert elf.encoding == EIData.Msb
    assert elf.machine == EMachine.Arm
    assert elf.interpreter is None
