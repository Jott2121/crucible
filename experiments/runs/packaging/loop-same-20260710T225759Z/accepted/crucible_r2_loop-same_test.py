import io
import struct

import pytest

from packaging._elffile import ELFFile


# Correct (original) format strings, as documented in the source module.
CORRECT_E_FMTS = {
    (1, 1): "<HHIIIIIHHH",
    (1, 2): ">HHIIIIIHHH",
    (2, 1): "<HHIQQQIHHH",
    (2, 2): ">HHIQQQIHHH",
}

CORRECT_P_FMTS = {
    (1, 1): "<IIIIIIII",
    (1, 2): ">IIIIIIII",
    (2, 1): "<IIQQQQQQ",
    (2, 2): ">IIQQQQQQ",
}


def _build_elf(capacity, encoding, machine, flags, phoff, phentsize, phnum):
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding] + [0] * 10)
    e_fmt = CORRECT_E_FMTS[(capacity, encoding)]
    header = struct.pack(
        e_fmt,
        0,          # e_type
        machine,    # e_machine
        0,          # e_version
        0,          # e_entry
        phoff,      # e_phoff
        0,          # e_shoff
        flags,      # e_flags
        0,          # e_ehsize
        phentsize,  # e_phentsize
        phnum,      # e_phnum
    )
    return ident + header


def test_64bit_lsb_header_fields_are_unsigned():
    # machine (H, 2 bytes) and flags (I, 4 bytes) have their high bit set.
    # If parsed as signed (mutants that lowercase the format), these would
    # come out negative instead of matching the values we packed in.
    machine_val = 0x8001          # 32769
    flags_val = 0x80000001        # 2147483649

    data = _build_elf(
        capacity=2, encoding=1,
        machine=machine_val, flags=flags_val,
        phoff=0, phentsize=0, phnum=0,
    )
    elf = ELFFile(io.BytesIO(data))

    assert elf.machine == machine_val
    assert elf.flags == flags_val


def test_64bit_msb_header_fields_are_unsigned():
    machine_val = 0x8001
    flags_val = 0x80000001

    data = _build_elf(
        capacity=2, encoding=2,
        machine=machine_val, flags=flags_val,
        phoff=0, phentsize=0, phnum=0,
    )
    elf = ELFFile(io.BytesIO(data))

    assert elf.machine == machine_val
    assert elf.flags == flags_val


def _check_p_fmt_unsigned(capacity, encoding):
    e_fmt = CORRECT_E_FMTS[(capacity, encoding)]
    p_fmt = CORRECT_P_FMTS[(capacity, encoding)]
    header_size = struct.calcsize(e_fmt)
    ph_size = struct.calcsize(p_fmt)
    phoff = 16 + header_size  # right after ident + header

    if capacity == 1:
        # 32-bit program header: 8 unsigned 4-byte fields.
        # idx = (0, 1, 4) -> p_type, p_offset, p_filesz
        p_offset = 0x80000001  # high bit set -> negative if read as signed
        p_filesz = 0x80000002
        values = [3, p_offset, 0, 0, p_filesz, 0, 0, 0]
    else:
        # 64-bit program header: I, I, Q, Q, Q, Q, Q, Q
        # idx = (0, 2, 5) -> p_type, p_offset, p_filesz
        p_offset = 0x8000000000000001
        p_filesz = 0x8000000000000002
        values = [3, 0, p_offset, 0, 0, p_filesz, 0, 0]

    ph_bytes = struct.pack(p_fmt, *values)

    data = _build_elf(
        capacity, encoding,
        machine=0, flags=0,
        phoff=phoff, phentsize=ph_size, phnum=1,
    )
    data += ph_bytes

    elf = ELFFile(io.BytesIO(data))

    # Directly exercise the parsed program-header format used internally.
    elf._f.seek(elf._e_phoff)
    raw = elf._f.read(struct.calcsize(elf._p_fmt))
    parsed = struct.unpack(elf._p_fmt, raw)

    idx = elf._p_idx
    assert parsed[idx[1]] == p_offset
    assert parsed[idx[2]] == p_filesz


def test_32bit_lsb_program_header_fields_are_unsigned():
    _check_p_fmt_unsigned(1, 1)


def test_32bit_msb_program_header_fields_are_unsigned():
    _check_p_fmt_unsigned(1, 2)


def test_64bit_lsb_program_header_fields_are_unsigned():
    _check_p_fmt_unsigned(2, 1)


def test_64bit_msb_program_header_fields_are_unsigned():
    _check_p_fmt_unsigned(2, 2)
