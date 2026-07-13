import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid, EIClass, EIData, EMachine


def _build_ident(capacity: int, encoding: int) -> bytes:
    return b"\x7fELF" + bytes([capacity, encoding]) + b"\x00" * 10


def _build_elf32_lsb(e_phoff=0, e_phentsize=0, e_phnum=0, machine=62, flags=0):
    ident = _build_ident(1, 1)
    e_fmt = "<HHIIIIIHHH"
    header = struct.pack(
        e_fmt,
        2,          # e_type
        machine,    # e_machine
        1,          # e_version
        0,          # e_entry
        e_phoff,    # e_phoff
        0,          # e_shoff
        flags,      # e_flags
        struct.calcsize(e_fmt) + 16,  # e_ehsize
        e_phentsize,  # e_phentsize
        e_phnum,      # e_phnum
    )
    return ident + header


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


def test_invalid_magic_raises():
    data = b"NOTELF" + b"\x00" * 10
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_too_short_ident_raises():
    data = b"\x7fELF"  # only 4 bytes, ident read expects 16
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_invalid_capacity_encoding_raises():
    ident = _build_ident(3, 1)  # capacity 3 is not a recognized value
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(ident))


def test_valid_32bit_lsb_header_parses_machine_and_flags():
    data = _build_elf32_lsb(machine=62, flags=1234)
    elf = ELFFile(io.BytesIO(data))
    assert elf.capacity == EIClass.C32
    assert elf.encoding == EIData.Lsb
    assert elf.machine == 62
    assert elf.flags == 1234


def test_interpreter_none_when_no_program_headers():
    data = _build_elf32_lsb(e_phoff=0, e_phentsize=0, e_phnum=0)
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter is None


def test_interpreter_found():
    e_fmt = "<HHIIIIIHHH"
    ehsize = struct.calcsize(e_fmt) + 16  # header size
    p_fmt = "<IIIIIIII"
    p_size = struct.calcsize(p_fmt)
    e_phoff = ehsize
    interp_offset = e_phoff + p_size
    interp_bytes = b"/lib/ld-linux.so.2\x00"

    ident = _build_ident(1, 1)
    header = struct.pack(
        e_fmt,
        2, 62, 1, 0, e_phoff, 0, 0, ehsize, p_size, 1,
    )
    prog_header = struct.pack(
        p_fmt,
        3,                  # p_type = PT_INTERP
        interp_offset,      # p_offset
        0,                  # p_vaddr
        0,                  # p_paddr
        len(interp_bytes),  # p_filesz
        0,                  # p_memsz
        0,                  # p_flags
        0,                  # p_align
    )
    data = ident + header + prog_header + interp_bytes
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == "/lib/ld-linux.so.2"


def test_interpreter_skips_non_interp_segment():
    e_fmt = "<HHIIIIIHHH"
    ehsize = struct.calcsize(e_fmt) + 16
    p_fmt = "<IIIIIIII"
    p_size = struct.calcsize(p_fmt)
    e_phoff = ehsize

    ident = _build_ident(1, 1)
    header = struct.pack(
        e_fmt,
        2, 62, 1, 0, e_phoff, 0, 0, ehsize, p_size, 1,
    )
    prog_header = struct.pack(
        p_fmt,
        1,  # p_type = PT_LOAD, not PT_INTERP
        0, 0, 0, 0, 0, 0, 0,
    )
    data = ident + header + prog_header
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter is None
