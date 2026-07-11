import io
import struct

import pytest

from packaging._elffile import EIClass, EIData, ELFFile, ELFInvalid, EMachine


# ---------------------------------------------------------------------------
# Helpers to build minimal, valid-enough ELF byte streams for testing.
# ---------------------------------------------------------------------------


def _ident(capacity: int, encoding: int) -> bytes:
    return b"\x7fELF" + bytes([capacity, encoding]) + bytes(10)


def build_elf32(
    e_machine: int = 3,
    e_flags: int = 0,
    interp: bytes | None = None,
) -> bytes:
    """Build a 32-bit LSB ELF, optionally with a PT_INTERP program header."""
    ident = _ident(1, 1)
    e_phoff = 16 + 30  # right after the ELF header
    phnum = 1 if interp is not None else 0

    ehdr = struct.pack(
        "<HHIIIIIHHH",
        2,  # e_type
        e_machine,
        1,  # e_version
        0,  # e_entry
        e_phoff,
        0,  # e_shoff
        e_flags,
        52,  # e_ehsize
        32,  # e_phentsize
        phnum,
    )

    if interp is None:
        return ident + ehdr

    p_offset = e_phoff + 32  # right after the single program header
    p_filesz = len(interp)
    phdr = struct.pack(
        "<IIIIIIII",
        3,  # p_type = PT_INTERP
        p_offset,
        0,  # p_vaddr
        0,  # p_paddr
        p_filesz,
        0,  # p_flags
        0,  # p_memsz
        0,  # p_align
    )
    return ident + ehdr + phdr + interp


def build_elf64_msb(
    e_machine: int = 183,
    e_flags: int = 0,
    interp: bytes | None = None,
) -> bytes:
    """Build a 64-bit MSB ELF, optionally with a PT_INTERP program header."""
    ident = _ident(2, 2)
    e_phoff = 16 + 42  # right after the ELF header
    phnum = 1 if interp is not None else 0

    ehdr = struct.pack(
        ">HHIQQQIHHH",
        2,  # e_type
        e_machine,
        1,  # e_version
        0,  # e_entry
        e_phoff,
        0,  # e_shoff
        e_flags,
        64,  # e_ehsize
        56,  # e_phentsize
        phnum,
    )

    if interp is None:
        return ident + ehdr

    p_offset = e_phoff + 56
    p_filesz = len(interp)
    phdr = struct.pack(
        ">IIQQQQQQ",
        3,  # p_type = PT_INTERP
        0,  # p_flags
        p_offset,
        0,  # p_vaddr
        0,  # p_paddr
        p_filesz,
        0,  # p_memsz
        0,  # p_align
    )
    return ident + ehdr + phdr + interp


# ---------------------------------------------------------------------------
# Enum value tests (spec constants).
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
# Invalid input handling.
# ---------------------------------------------------------------------------


def test_invalid_magic_raises():
    data = b"NOTELF" + bytes(10)  # 16 bytes total, wrong magic
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_truncated_ident_raises():
    data = b"\x7fELF"  # only 4 bytes, cannot read full 16-byte ident
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_unrecognized_capacity_encoding_raises():
    # capacity=3 is not a valid EIClass value.
    data = _ident(3, 1)
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


def test_truncated_ehdr_raises():
    # Valid ident, but nothing follows for the ELF header itself.
    data = _ident(1, 1)
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(data))


# ---------------------------------------------------------------------------
# 32-bit LSB tests.
# ---------------------------------------------------------------------------


def test_elf32_basic_fields():
    data = build_elf32(e_machine=3, e_flags=7)
    elf = ELFFile(io.BytesIO(data))
    assert elf.capacity == 1
    assert elf.encoding == 1
    assert elf.machine == 3
    assert elf.flags == 7


def test_elf32_no_interp_returns_none():
    data = build_elf32(interp=None)
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter is None


def test_elf32_interp_returns_path():
    interp_path = b"/lib/ld-linux.so.2"
    data = build_elf32(interp=interp_path)
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == "/lib/ld-linux.so.2"


def test_elf32_interp_strips_null_bytes():
    interp_path = b"/lib/ld-linux.so.2\0\0\0"
    data = build_elf32(interp=interp_path)
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == "/lib/ld-linux.so.2"


# ---------------------------------------------------------------------------
# 64-bit MSB tests.
# ---------------------------------------------------------------------------


def test_elf64_msb_basic_fields():
    data = build_elf64_msb(e_machine=183, e_flags=42)
    elf = ELFFile(io.BytesIO(data))
    assert elf.capacity == 2
    assert elf.encoding == 2
    assert elf.machine == 183
    assert elf.flags == 42


def test_elf64_msb_no_interp_returns_none():
    data = build_elf64_msb(interp=None)
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter is None


def test_elf64_msb_interp_returns_path():
    interp_path = b"/lib64/ld-linux-x86-64.so.2"
    data = build_elf64_msb(interp=interp_path)
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == "/lib64/ld-linux-x86-64.so.2"


def test_elf64_msb_empty_interp_string():
    data = build_elf64_msb(interp=b"")
    elf = ELFFile(io.BytesIO(data))
    assert elf.interpreter == ""
