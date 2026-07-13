import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid, EIClass, EIData, EMachine


def build_elf32_lsb_with_interp(interp_path: bytes) -> bytes:
    """
    Manually construct a minimal valid 32-bit LSB ELF file with a single
    PT_INTERP program header pointing at `interp_path`.
    """
    # ELF identification (16 bytes)
    ident = bytes([0x7F, ord("E"), ord("L"), ord("F"), 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    assert len(ident) == 16

    e_fmt = "<HHIIIIIHHH"
    p_fmt = "<IIIIIIII"

    # Layout: ident(16) + ehdr + phdr(1 entry) + interp string
    ehdr_size = struct.calcsize(e_fmt)
    phdr_size = struct.calcsize(p_fmt)

    e_phoff = 16 + ehdr_size
    interp_offset = e_phoff + phdr_size
    interp_bytes = interp_path + b"\x00"

    ehdr = struct.pack(
        e_fmt,
        2,       # e_type
        3,       # e_machine placeholder overridden below via EMachine value
        1,       # e_version
        0,       # e_entry
        e_phoff, # e_phoff
        0,       # e_shoff
        0,       # e_flags
        0,       # e_ehsize
        phdr_size,  # e_phentsize
        1,       # e_phnum
    )

    # p_type=3 (PT_INTERP), p_offset=interp_offset, ... p_filesz=len(interp_bytes)
    phdr = struct.pack(
        p_fmt,
        3,               # p_type = PT_INTERP
        interp_offset,   # p_offset
        0,               # p_vaddr
        0,               # p_paddr
        len(interp_bytes),  # p_filesz
        0,               # p_memsz
        0,               # p_flags
        0,               # p_align
    )

    return ident + ehdr + phdr + interp_bytes


def test_valid_magic_parses_successfully():
    data = build_elf32_lsb_with_interp(b"/lib/ld-linux.so.2")
    f = io.BytesIO(data)
    elf = ELFFile(f)
    assert elf.capacity == EIClass.C32
    assert elf.encoding == EIData.Lsb


def test_invalid_magic_raises_elfinvalid():
    # Corrupt the very first magic byte so it no longer matches b"\x7fELF"
    data = bytearray(build_elf32_lsb_with_interp(b"/lib/ld-linux.so.2"))
    data[0] = 0x00  # not 0x7F anymore
    f = io.BytesIO(bytes(data))
    with pytest.raises(ELFInvalid):
        ELFFile(f)


def test_magic_byte_is_exactly_0x7f():
    # Directly verify the expected magic byte value used by the parser.
    data = build_elf32_lsb_with_interp(b"/lib/ld-linux.so.2")
    assert data[0] == 0x7F
    assert data[0] == 127


def test_interpreter_reads_correct_path():
    interp_path = b"/lib64/ld-linux-x86-64.so.2"
    data = build_elf32_lsb_with_interp(interp_path)
    f = io.BytesIO(data)
    elf = ELFFile(f)
    assert elf.interpreter == interp_path.decode("ascii")


def test_too_short_file_raises_elfinvalid():
    # Not enough bytes even for the identification header.
    f = io.BytesIO(b"\x7fELF\x01\x01\x00\x00")
    with pytest.raises(ELFInvalid):
        ELFFile(f)


def test_unrecognized_capacity_encoding_raises_elfinvalid():
    # Valid magic, but invalid capacity/encoding combination (both zero).
    ident = bytes([0x7F, ord("E"), ord("L"), ord("F"), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    f = io.BytesIO(ident)
    with pytest.raises(ELFInvalid):
        ELFFile(f)
