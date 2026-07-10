import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


def _build_elf(capacity, encoding, machine=99, flags=0x1234, interp=b"/lib64/ld-linux.so"):
    """Construct a minimal but well-formed ELF file with a PT_INTERP entry."""
    if capacity == 1:
        e_fmt = "<HHIIIIIHHH" if encoding == 1 else ">HHIIIIIHHH"
        p_fmt = "<IIIIIIII" if encoding == 1 else ">IIIIIIII"
    else:
        e_fmt = "<HHIQQQIHHH" if encoding == 1 else ">HHIQQQIHHH"
        p_fmt = "<IIQQQQQQ" if encoding == 1 else ">IIQQQQQQ"

    ident = bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding] + [0] * 10)
    header_size = struct.calcsize(e_fmt)
    phentsize = struct.calcsize(p_fmt)
    e_phoff = 16 + header_size
    e_phnum = 1

    header = struct.pack(
        e_fmt, 2, machine, 1, 0, e_phoff, 0, flags, 0, phentsize, e_phnum
    )

    interp_offset = e_phoff + phentsize
    interp_bytes = interp + b"\x00"
    filesz = len(interp_bytes)

    if capacity == 1:
        # p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align
        pheader = struct.pack(p_fmt, 3, interp_offset, 0, 0, filesz, 0, 0, 0)
    else:
        # p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align
        pheader = struct.pack(p_fmt, 3, 0, interp_offset, 0, 0, filesz, 0, 0)

    return ident + header + pheader + interp_bytes


@pytest.mark.parametrize("capacity,encoding", [(1, 1), (1, 2), (2, 1), (2, 2)])
def test_elf_roundtrip_all_formats(capacity, encoding):
    data = _build_elf(capacity, encoding, machine=99, flags=0x1234)
    elf = ELFFile(io.BytesIO(data))

    assert elf.capacity == capacity
    assert elf.encoding == encoding
    assert elf.machine == 99
    assert elf.flags == 0x1234
    assert elf.interpreter == "/lib64/ld-linux.so"


def test_encoding_uses_ident_index_5_not_6():
    # capacity at ident[4] = 1 (valid), encoding at ident[5] = 1 (valid LSB),
    # but ident[6] is set to an invalid pseudo-encoding value (3).
    # If the code mistakenly reads ident[6] for encoding, it will raise
    # ELFInvalid because (capacity=1, encoding=3) is not a valid combination.
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, 1, 1, 3] + [0] * 9)
    e_fmt = "<HHIIIIIHHH"
    header = struct.pack(e_fmt, 2, 99, 1, 0, 100, 0, 0x55, 0, 32, 0)
    data = ident + header

    elf = ELFFile(io.BytesIO(data))
    assert elf.encoding == 1
    assert elf.machine == 99


def test_invalid_magic_message():
    data = b"XXXX" + b"\x00" * 12
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(data))
    assert str(excinfo.value) == f"invalid magic: {b'XXXX'!r}"


def test_unable_to_parse_identification_message():
    # Fewer than 16 bytes causes struct.error while reading ident.
    data = b"\x7fEL"
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(data))
    assert str(excinfo.value) == "unable to parse identification"


def test_unrecognized_capacity_or_encoding_message():
    # capacity=3, encoding=1 is not a recognized combination.
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, 3, 1] + [0] * 10)
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(ident))
    assert str(excinfo.value) == "unrecognized capacity (3) or encoding (1)"


def test_unable_to_parse_machine_and_section_information_message():
    # Valid ident (capacity=1, encoding=1) but truncated body so that
    # reading the e_fmt fields fails with struct.error.
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, 1, 1] + [0] * 10)
    data = ident + b"\x00\x00"  # way too short for "<HHIIIIIHHH"
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(data))
    assert str(excinfo.value) == "unable to parse machine and section information"
