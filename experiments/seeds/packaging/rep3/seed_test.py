import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid, EIClass, EIData, EMachine


def _elf32_lsb_with_interp():
    # ---- ELF header (32-bit, LSB) ----
    ident = struct.pack(
        "16B",
        0x7F, 0x45, 0x4C, 0x46,  # magic \x7fELF
        1,  # capacity = C32
        1,  # encoding = Lsb
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    )
    phoff = 46  # 16 (ident) + 30 (rest of header)
    phentsize = 32
    phnum = 2
    rest = struct.pack(
        "<HHIIIIIHHH",
        2,  # e_type
        3,  # e_machine = I386
        1,  # e_version
        0,  # e_entry
        phoff,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        52,  # e_ehsize
        phentsize,  # e_phentsize
        phnum,  # e_phnum
    )
    # Program header 0: not PT_INTERP
    ph0 = struct.pack("<IIIIIIII", 1, 0, 0, 0, 0, 0, 0, 0)

    interp_offset = phoff + phentsize * phnum  # 46 + 64 = 110
    interp_bytes = b"/lib/ld-linux.so.2\x00"
    filesz = len(interp_bytes)

    # Program header 1: PT_INTERP (type == 3)
    ph1 = struct.pack(
        "<IIIIIIII", 3, interp_offset, 0, 0, filesz, 0, 0, 0
    )

    data = ident + rest + ph0 + ph1 + interp_bytes
    return data


def _elf32_lsb_without_interp():
    ident = struct.pack(
        "16B",
        0x7F, 0x45, 0x4C, 0x46,
        1,  # capacity = C32
        1,  # encoding = Lsb
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    )
    phoff = 46
    phentsize = 32
    phnum = 1
    rest = struct.pack(
        "<HHIIIIIHHH",
        2, 3, 1, 0, phoff, 0, 0, 52, phentsize, phnum,
    )
    # Only one program header, not PT_INTERP
    ph0 = struct.pack("<IIIIIIII", 1, 0, 0, 0, 0, 0, 0, 0)
    data = ident + rest + ph0
    return data


def _elf64_msb_with_interp():
    ident = struct.pack(
        "16B",
        0x7F, 0x45, 0x4C, 0x46,
        2,  # capacity = C64
        2,  # encoding = Msb
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    )
    phoff = 58  # 16 (ident) + 42 (rest of header)
    phentsize = 56
    phnum = 2
    rest = struct.pack(
        ">HHIQQQIHHH",
        2,  # e_type
        183,  # e_machine = AArch64
        1,  # e_version
        0,  # e_entry
        phoff,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        64,  # e_ehsize
        phentsize,
        phnum,
    )
    ph0 = struct.pack(">IIQQQQQQ", 1, 0, 0, 0, 0, 0, 0, 0)

    interp_offset = phoff + phentsize * phnum  # 58 + 112 = 170
    interp_bytes = b"/usr/lib/ld64.so.1\x00"
    filesz = len(interp_bytes)

    ph1 = struct.pack(">IIQQQQQQ", 3, 0, interp_offset, 0, 0, filesz, 0, 0)

    data = ident + rest + ph0 + ph1 + interp_bytes
    return data


def test_elf32_lsb_basic_attributes():
    data = _elf32_lsb_with_interp()
    elf = ELFFile(io.BytesIO(data))
    assert elf.capacity == EIClass.C32
    assert elf.encoding == EIData.Lsb
    assert elf.machine == EMachine.I386
    assert elf.flags == 0


def test_elf32_lsb_interpreter_found():
    data = _elf32_lsb_with_interp()
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == "/lib/ld-linux.so.2"


def test_elf32_lsb_no_interpreter():
    data = _elf32_lsb_without_interp()
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter is None


def test_elf64_msb_basic_attributes():
    data = _elf64_msb_with_interp()
    elf = ELFFile(io.BytesIO(data))
    assert elf.capacity == EIClass.C64
    assert elf.encoding == EIData.Msb
    assert elf.machine == EMachine.AArch64
    assert elf.flags == 0


def test_elf64_msb_interpreter_found():
    data = _elf64_msb_with_interp()
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == "/usr/lib/ld64.so.1"


def test_invalid_too_short_for_ident():
    # Fewer than 16 bytes -> struct.error while parsing ident.
    data = b"\x7fELF"
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_invalid_magic():
    # Valid length (16 bytes) but wrong magic bytes.
    data = struct.pack(
        "16B",
        0, 0, 0, 0,  # wrong magic
        1, 1,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    )
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_invalid_capacity_encoding_combo():
    # Correct magic, but capacity/encoding combination not recognized.
    data = struct.pack(
        "16B",
        0x7F, 0x45, 0x4C, 0x46,
        3,  # invalid capacity
        1,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    )
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_invalid_truncated_machine_section():
    # Valid ident (16 bytes, capacity=1, encoding=1) but not enough data
    # remaining to parse the rest of the ELF header.
    ident = struct.pack(
        "16B",
        0x7F, 0x45, 0x4C, 0x46,
        1,  # capacity = C32
        1,  # encoding = Lsb
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    )
    truncated_rest = b"\x00\x00\x00"  # far fewer than the required 30 bytes
    data = ident + truncated_rest
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_enum_values():
    assert EIClass.C32 == 1
    assert EIClass.C64 == 2
    assert EIData.Lsb == 1
    assert EIData.Msb == 2
    assert EMachine.I386 == 3
    assert EMachine.S390 == 22
    assert EMachine.Arm == 40
    assert EMachine.X8664 == 62
    assert EMachine.AArch64 == 183
