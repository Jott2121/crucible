import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid, EIClass, EIData, EMachine


# ---------------------------------------------------------------------------
# Enum value tests (boundary / exact values from spec)
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
    # 16 bytes total (matches "16B" format) but wrong magic.
    data = b"X" * 16
    f = io.BytesIO(data)
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(f)
    assert "invalid magic" in str(excinfo.value)


def test_too_short_for_identification_raises():
    # Fewer than 16 bytes -> struct.error while parsing ident.
    data = b"\x7fELF"
    f = io.BytesIO(data)
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(f)
    assert "unable to parse identification" in str(excinfo.value)


def test_unrecognized_capacity_encoding_raises():
    # Valid magic, but capacity=3 (not 1 or 2) is not in the lookup table.
    ident = b"\x7fELF" + bytes([3, 1]) + b"\x00" * 10
    f = io.BytesIO(ident)
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(f)
    assert "unrecognized capacity (3) or encoding (1)" in str(excinfo.value)


def test_unrecognized_encoding_raises():
    # Valid magic, capacity=1 (valid) but encoding=3 (not 1 or 2).
    ident = b"\x7fELF" + bytes([1, 3]) + b"\x00" * 10
    f = io.BytesIO(ident)
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(f)
    assert "unrecognized capacity (1) or encoding (3)" in str(excinfo.value)


def test_truncated_after_ident_raises():
    # Valid ident (32-bit LSB) but not enough bytes for the ELF header itself.
    ident = b"\x7fELF" + bytes([1, 1]) + b"\x00" * 10
    f = io.BytesIO(ident)  # nothing more to read
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(f)
    assert "unable to parse machine and section information" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Valid ELF construction helpers
# ---------------------------------------------------------------------------


def _build_64le_elf(machine, flags, phoff, phentsize, phnum, extra=b""):
    ident = b"\x7fELF" + bytes([2, 1]) + b"\x00" * 10  # 64-bit, LSB
    header = struct.pack(
        "<HHIQQQIHHH",
        1,  # e_type
        machine,  # e_machine
        1,  # e_version
        0,  # e_entry
        phoff,  # e_phoff
        0,  # e_shoff
        flags,  # e_flags
        64,  # e_ehsize
        phentsize,  # e_phentsize
        phnum,  # e_phnum
    )
    return ident + header + extra


def test_valid_64bit_lsb_no_program_headers():
    machine = EMachine.X8664
    flags = 0x1234
    phentsize = struct.calcsize("<IIQQQQQQ")
    data = _build_64le_elf(machine, flags, phoff=58, phentsize=phentsize, phnum=0)
    f = io.BytesIO(data)
    elf = ELFFile(f)

    assert elf.capacity == EIClass.C64
    assert elf.encoding == EIData.Lsb
    assert elf.machine == machine
    assert elf.flags == flags
    assert elf.interpreter is None


def test_valid_64bit_lsb_with_interpreter():
    machine = EMachine.AArch64
    flags = 0
    phentsize = struct.calcsize("<IIQQQQQQ")
    header_size = 16 + struct.calcsize("<HHIQQQIHHH")  # 16 + 42 = 58
    phoff = header_size
    interp_bytes = b"/lib64/ld-linux-aarch64.so.1\x00"
    interp_offset = phoff + phentsize

    phdr = struct.pack(
        "<IIQQQQQQ",
        3,  # p_type: PT_INTERP
        0,  # p_flags
        interp_offset,  # p_offset
        0,  # p_vaddr
        0,  # p_paddr
        len(interp_bytes),  # p_filesz
        0,  # p_memsz
        0,  # p_align
    )

    data = _build_64le_elf(
        machine, flags, phoff=phoff, phentsize=phentsize, phnum=1, extra=phdr + interp_bytes
    )
    f = io.BytesIO(data)
    elf = ELFFile(f)

    assert elf.machine == machine
    assert elf.interpreter == "/lib64/ld-linux-aarch64.so.1"


def _build_32be_elf(machine, flags, phoff, phentsize, phnum, extra=b""):
    ident = b"\x7fELF" + bytes([1, 2]) + b"\x00" * 10  # 32-bit, MSB
    header = struct.pack(
        ">HHIIIIIHHH",
        1,  # e_type
        machine,  # e_machine
        1,  # e_version
        0,  # e_entry
        phoff,  # e_phoff
        0,  # e_shoff
        flags,  # e_flags
        52,  # e_ehsize
        phentsize,  # e_phentsize
        phnum,  # e_phnum
    )
    return ident + header + extra


def test_valid_32bit_msb_no_program_headers():
    machine = EMachine.Arm
    flags = 7
    phentsize = struct.calcsize(">IIIIIIII")
    data = _build_32be_elf(machine, flags, phoff=52 + 16, phentsize=phentsize, phnum=0)
    f = io.BytesIO(data)
    elf = ELFFile(f)

    assert elf.capacity == EIClass.C32
    assert elf.encoding == EIData.Msb
    assert elf.machine == machine
    assert elf.flags == flags
    assert elf.interpreter is None


def test_valid_32bit_msb_with_interpreter():
    machine = EMachine.I386
    flags = 0
    phentsize = struct.calcsize(">IIIIIIII")
    header_size = 16 + struct.calcsize(">HHIIIIIHHH")  # 16 + 26 = 42
    phoff = header_size
    interp_bytes = b"/lib/ld-linux.so.2\x00"
    interp_offset = phoff + phentsize

    phdr = struct.pack(
        ">IIIIIIII",
        3,  # p_type: PT_INTERP
        interp_offset,  # p_offset (index 1 for 32-bit)
        0,  # p_vaddr
        0,  # p_paddr
        len(interp_bytes),  # p_filesz (index 4)
        0,  # p_memsz
        0,  # p_flags
        0,  # p_align
    )

    data = _build_32be_elf(
        machine, flags, phoff=phoff, phentsize=phentsize, phnum=1, extra=phdr + interp_bytes
    )
    f = io.BytesIO(data)
    elf = ELFFile(f)

    assert elf.machine == machine
    assert elf.interpreter == "/lib/ld-linux.so.2"


def test_interpreter_skips_non_interp_program_headers():
    # A single program header whose p_type is NOT 3 (PT_INTERP) -> interpreter is None.
    machine = EMachine.X8664
    flags = 0
    phentsize = struct.calcsize("<IIQQQQQQ")
    header_size = 16 + struct.calcsize("<HHIQQQIHHH")
    phoff = header_size

    phdr = struct.pack(
        "<IIQQQQQQ",
        1,  # p_type: PT_LOAD (not PT_INTERP)
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )

    data = _build_64le_elf(machine, flags, phoff=phoff, phentsize=phentsize, phnum=1, extra=phdr)
    f = io.BytesIO(data)
    elf = ELFFile(f)

    assert elf.interpreter is None

