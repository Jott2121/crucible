import io
import struct

import pytest

from packaging._elffile import EIClass, EIData, EMachine, ELFFile, ELFInvalid


# ---------------------------------------------------------------------------
# Enum value tests (contract values taken directly from the docstring/spec).
# ---------------------------------------------------------------------------


def test_ei_class_values():
    assert EIClass.C32 == 1
    assert EIClass.C64 == 2


def test_ei_data_values():
    assert EIData.Lsb == 1
    assert EIData.Msb == 2


def test_e_machine_values():
    assert EMachine.I386 == 3
    assert EMachine.S390 == 22
    assert EMachine.Arm == 40
    assert EMachine.X8664 == 62
    assert EMachine.AArch64 == 183


# ---------------------------------------------------------------------------
# Error handling.
# ---------------------------------------------------------------------------


def test_invalid_magic_raises():
    # 16 bytes of identification, but wrong magic.
    data = b"NOTELF\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    assert len(data) == 16
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_truncated_ident_raises():
    # Fewer than 16 bytes -> struct.error internally -> ELFInvalid.
    data = b"\x7fELF"
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_unrecognized_capacity_encoding_raises():
    # capacity=3 (invalid), encoding=1
    ident = b"\x7fELF" + bytes([3, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    assert len(ident) == 16
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(ident))


def test_truncated_elf_header_raises():
    # Valid ident (32-bit LSB) but header cut off before full e_fmt read.
    ident = b"\x7fELF" + bytes([1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    # Only append a couple of bytes of the header, not the full 30 bytes needed.
    data = ident + b"\x00\x00"
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


# ---------------------------------------------------------------------------
# Helpers to build synthetic ELF files.
# ---------------------------------------------------------------------------


def _build_32bit_lsb_elf(e_phnum, e_phoff, phdrs=b"", extra=b""):
    ident = b"\x7fELF" + bytes([1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    assert len(ident) == 16

    e_fmt = "<HHIIIIIHHH"
    header = struct.pack(
        e_fmt,
        2,       # e_type
        40,      # e_machine (Arm)
        1,       # e_version
        0,       # e_entry
        e_phoff, # e_phoff
        0,       # e_shoff
        1234,    # e_flags
        52,      # e_ehsize
        32,      # e_phentsize
        e_phnum, # e_phnum
    )
    return ident + header, extra


def test_32bit_lsb_header_fields_no_interp():
    header_size = struct.calcsize("<HHIIIIIHHH")
    ident_size = 16
    e_phoff = ident_size + header_size
    ident_and_header, _ = _build_32bit_lsb_elf(e_phnum=0, e_phoff=e_phoff)

    f = io.BytesIO(ident_and_header)
    elf = ELFFile(f)

    assert elf.capacity == EIClass.C32
    assert elf.encoding == EIData.Lsb
    assert elf.machine == EMachine.Arm
    assert elf.flags == 1234
    assert elf.interpreter is None


def test_32bit_lsb_with_pt_interp():
    header_size = struct.calcsize("<HHIIIIIHHH")
    ident_size = 16
    e_phoff = ident_size + header_size
    p_fmt = "<IIIIIIII"
    phentsize = struct.calcsize(p_fmt)

    interp_str = b"/lib/ld-linux.so.2\x00"
    interp_offset = e_phoff + phentsize

    phdr = struct.pack(
        p_fmt,
        3,                 # p_type = PT_INTERP
        interp_offset,     # p_offset
        0,                 # p_vaddr
        0,                 # p_paddr
        len(interp_str),   # p_filesz
        0,                 # p_memsz
        0,                 # p_flags
        0,                 # p_align
    )

    ident = b"\x7fELF" + bytes([1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    e_fmt = "<HHIIIIIHHH"
    header = struct.pack(
        e_fmt,
        2,          # e_type
        62,         # e_machine (X8664, arbitrary here)
        1,          # e_version
        0,          # e_entry
        e_phoff,    # e_phoff
        0,          # e_shoff
        0,          # e_flags
        52,         # e_ehsize
        phentsize,  # e_phentsize
        1,          # e_phnum
    )

    data = ident + header + phdr + interp_str
    f = io.BytesIO(data)
    elf = ELFFile(f)

    assert elf.interpreter == "/lib/ld-linux.so.2"


def test_64bit_lsb_with_pt_interp():
    ident = b"\x7fELF" + bytes([2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    e_fmt = "<HHIQQQIHHH"
    p_fmt = "<IIQQQQQQ"

    header_size = struct.calcsize(e_fmt)
    ident_size = 16
    e_phoff = ident_size + header_size
    phentsize = struct.calcsize(p_fmt)

    interp_str = b"/bin/sh\x00"
    interp_offset = e_phoff + phentsize

    phdr = struct.pack(
        p_fmt,
        3,               # p_type = PT_INTERP
        0,               # p_flags
        interp_offset,   # p_offset
        0,               # p_vaddr
        0,               # p_paddr
        len(interp_str), # p_filesz
        0,               # p_memsz
        0,               # p_align
    )

    header = struct.pack(
        e_fmt,
        2,          # e_type
        183,        # e_machine (AArch64)
        1,          # e_version
        0,          # e_entry
        e_phoff,    # e_phoff
        0,          # e_shoff
        0,          # e_flags
        64,         # e_ehsize
        phentsize,  # e_phentsize
        1,          # e_phnum
    )

    data = ident + header + phdr + interp_str
    f = io.BytesIO(data)
    elf = ELFFile(f)

    assert elf.capacity == EIClass.C64
    assert elf.encoding == EIData.Lsb
    assert elf.machine == EMachine.AArch64
    assert elf.interpreter == "/bin/sh"


def test_interpreter_none_when_no_program_headers():
    header_size = struct.calcsize("<HHIIIIIHHH")
    ident_size = 16
    e_phoff = ident_size + header_size
    ident_and_header, _ = _build_32bit_lsb_elf(e_phnum=0, e_phoff=e_phoff)

    f = io.BytesIO(ident_and_header)
    elf = ELFFile(f)
    # Accessing interpreter twice should be stable and return None both times.
    assert elf.interpreter is None
    assert elf.interpreter is None


def test_interpreter_skips_non_interp_segment():
    header_size = struct.calcsize("<HHIIIIIHHH")
    ident_size = 16
    e_phoff = ident_size + header_size
    p_fmt = "<IIIIIIII"
    phentsize = struct.calcsize(p_fmt)

    # A single PT_LOAD (type=1) segment, not PT_INTERP.
    phdr = struct.pack(
        p_fmt,
        1,   # p_type = PT_LOAD, not PT_INTERP
        0,   # p_offset
        0,   # p_vaddr
        0,   # p_paddr
        0,   # p_filesz
        0,   # p_memsz
        0,   # p_flags
        0,   # p_align
    )

    ident = b"\x7fELF" + bytes([1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    e_fmt = "<HHIIIIIHHH"
    header = struct.pack(
        e_fmt,
        2, 3, 1, 0, e_phoff, 0, 0, 52, phentsize, 1,
    )

    data = ident + header + phdr
    f = io.BytesIO(data)
    elf = ELFFile(f)

    assert elf.interpreter is None
