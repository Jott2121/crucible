import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid, EIClass, EIData, EMachine


# Same mapping as documented in the module's spec, used here only to build
# byte strings for test fixtures (never to call into the module for expected
# values).
_FORMATS = {
    (1, 1): ("<HHIIIIIHHH", "<IIIIIIII", (0, 1, 4)),  # 32-bit LSB.
    (1, 2): (">HHIIIIIHHH", ">IIIIIIII", (0, 1, 4)),  # 32-bit MSB.
    (2, 1): ("<HHIQQQIHHH", "<IIQQQQQQ", (0, 2, 5)),  # 64-bit LSB.
    (2, 2): (">HHIQQQIHHH", ">IIQQQQQQ", (0, 2, 5)),  # 64-bit MSB.
}


def _make_ident(capacity, encoding):
    return bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding]) + bytes(10)


def _build_elf(
    capacity,
    encoding,
    machine,
    flags=0,
    phdrs=None,
    strings=b"",
):
    """
    Build a minimal fake ELF file. `phdrs` is a list of dicts with keys
    p_type, p_offset, p_filesz (rest filled with zero), used to fill in
    a program header table located right after the ELF header.
    Offsets in phdrs are relative to the start of the string blob which
    is appended right after the program header table; caller should pass
    absolute offsets already computed.
    """
    e_fmt, p_fmt, p_idx = _FORMATS[(capacity, encoding)]
    ident = _make_ident(capacity, encoding)

    phnum = len(phdrs) if phdrs else 0
    phentsize = struct.calcsize(p_fmt) if phnum else 0
    header_size = len(ident) + struct.calcsize(e_fmt)
    phoff = header_size if phnum else 0

    header = ident + struct.pack(
        e_fmt,
        2,  # e_type
        machine,  # e_machine
        1,  # e_version
        0,  # e_entry
        phoff,  # e_phoff
        0,  # e_shoff
        flags,  # e_flags
        header_size,  # e_ehsize
        phentsize,  # e_phentsize
        phnum,  # e_phnum
    )

    phdr_bytes = b""
    if phdrs:
        for ph in phdrs:
            if capacity == 1:
                # p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align
                phdr_bytes += struct.pack(
                    p_fmt,
                    ph["p_type"],
                    ph["p_offset"],
                    0,
                    0,
                    ph["p_filesz"],
                    ph["p_filesz"],
                    0,
                    0,
                )
            else:
                # p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align
                phdr_bytes += struct.pack(
                    p_fmt,
                    ph["p_type"],
                    0,
                    ph["p_offset"],
                    0,
                    0,
                    ph["p_filesz"],
                    ph["p_filesz"],
                    0,
                )

    return header + phdr_bytes + strings


# --------------------------------------------------------------------------
# Enum value tests
# --------------------------------------------------------------------------


def test_eiclass_values():
    assert int(EIClass.C32) == 1
    assert int(EIClass.C64) == 2


def test_eidata_values():
    assert int(EIData.Lsb) == 1
    assert int(EIData.Msb) == 2


def test_emachine_values():
    assert int(EMachine.I386) == 3
    assert int(EMachine.S390) == 22
    assert int(EMachine.Arm) == 40
    assert int(EMachine.X8664) == 62
    assert int(EMachine.AArch64) == 183


# --------------------------------------------------------------------------
# Error handling
# --------------------------------------------------------------------------


def test_invalid_magic_raises():
    data = bytes(16)  # all zero, wrong magic
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_truncated_ident_raises():
    data = b"\x7fEL"  # fewer than 16 bytes
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_unrecognized_capacity_encoding_raises():
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, 9, 9]) + bytes(10)
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(ident))


def test_truncated_header_after_ident_raises():
    ident = _make_ident(1, 1)
    # No further bytes for the e_fmt header.
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(ident))


# --------------------------------------------------------------------------
# Basic field parsing
# --------------------------------------------------------------------------


def test_32bit_lsb_basic_fields_no_phdrs():
    data = _build_elf(1, 1, machine=int(EMachine.I386), flags=0x1234)
    elf = ELFFile(io.BytesIO(data))
    assert elf.capacity == 1
    assert elf.encoding == 1
    assert elf.machine == int(EMachine.I386)
    assert elf.flags == 0x1234
    assert elf.interpreter is None


def test_64bit_lsb_basic_fields_no_phdrs():
    data = _build_elf(2, 1, machine=int(EMachine.X8664), flags=0)
    elf = ELFFile(io.BytesIO(data))
    assert elf.capacity == 2
    assert elf.encoding == 1
    assert elf.machine == int(EMachine.X8664)
    assert elf.interpreter is None


# --------------------------------------------------------------------------
# Interpreter parsing
# --------------------------------------------------------------------------


def test_32bit_lsb_interpreter_found():
    e_fmt, p_fmt, p_idx = _FORMATS[(1, 1)]
    header_size = len(_make_ident(1, 1)) + struct.calcsize(e_fmt)
    phentsize = struct.calcsize(p_fmt)
    string_offset = header_size + phentsize
    interp = b"/lib/ld-linux.so.2\0"
    phdrs = [
        {"p_type": 3, "p_offset": string_offset, "p_filesz": len(interp)},
    ]
    data = _build_elf(
        1, 1, machine=int(EMachine.I386), phdrs=phdrs, strings=interp
    )
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == "/lib/ld-linux.so.2"


def test_64bit_lsb_interpreter_found():
    e_fmt, p_fmt, p_idx = _FORMATS[(2, 1)]
    header_size = len(_make_ident(2, 1)) + struct.calcsize(e_fmt)
    phentsize = struct.calcsize(p_fmt)
    string_offset = header_size + phentsize
    interp = b"/bin/sh\0"
    phdrs = [
        {"p_type": 3, "p_offset": string_offset, "p_filesz": len(interp)},
    ]
    data = _build_elf(
        2, 1, machine=int(EMachine.X8664), phdrs=phdrs, strings=interp
    )
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == "/bin/sh"


def test_interpreter_none_when_no_pt_interp_segment():
    e_fmt, p_fmt, p_idx = _FORMATS[(1, 1)]
    header_size = len(_make_ident(1, 1)) + struct.calcsize(e_fmt)
    phentsize = struct.calcsize(p_fmt)
    string_offset = header_size + phentsize
    data_str = b"ignored\0"
    # p_type = 1 (PT_LOAD), not PT_INTERP (3)
    phdrs = [
        {"p_type": 1, "p_offset": string_offset, "p_filesz": len(data_str)},
    ]
    data = _build_elf(
        1, 1, machine=int(EMachine.I386), phdrs=phdrs, strings=data_str
    )
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter is None


def test_interpreter_strips_multiple_trailing_nulls():
    e_fmt, p_fmt, p_idx = _FORMATS[(1, 1)]
    header_size = len(_make_ident(1, 1)) + struct.calcsize(e_fmt)
    phentsize = struct.calcsize(p_fmt)
    string_offset = header_size + phentsize
    interp = b"/bin/sh\0\0\0\0"
    phdrs = [
        {"p_type": 3, "p_offset": string_offset, "p_filesz": len(interp)},
    ]
    data = _build_elf(
        1, 1, machine=int(EMachine.I386), phdrs=phdrs, strings=interp
    )
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == "/bin/sh"


def test_interpreter_returns_first_matching_segment():
    e_fmt, p_fmt, p_idx = _FORMATS[(1, 1)]
    header_size = len(_make_ident(1, 1)) + struct.calcsize(e_fmt)
    phentsize = struct.calcsize(p_fmt)
    # Two program header entries.
    string_offset_base = header_size + phentsize * 2
    first_interp = b"/first\0"
    second_interp = b"/second\0"
    second_offset = string_offset_base + len(first_interp)
    phdrs = [
        {
            "p_type": 3,
            "p_offset": string_offset_base,
            "p_filesz": len(first_interp),
        },
        {
            "p_type": 3,
            "p_offset": second_offset,
            "p_filesz": len(second_interp),
        },
    ]
    data = _build_elf(
        1,
        1,
        machine=int(EMachine.I386),
        phdrs=phdrs,
        strings=first_interp + second_interp,
    )
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == "/first"
