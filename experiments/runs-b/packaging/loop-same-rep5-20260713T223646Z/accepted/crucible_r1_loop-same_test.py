import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


def _build_elf(capacity, encoding, e_fmt, p_fmt, machine, flags):
    """
    Construct a minimal-but-valid ELF byte string for the given
    capacity/encoding combination, with one PT_INTERP program header
    pointing at a known interpreter string.

    Returns (data_bytes, expected_interpreter_string).
    """
    ident = b"\x7fELF" + bytes([capacity, encoding]) + b"\x00" * 10
    assert len(ident) == 16

    ehsize = struct.calcsize(e_fmt)
    phentsize = struct.calcsize(p_fmt)
    phnum = 1
    e_phoff = len(ident) + ehsize

    interp = b"/lib/expected-interp.so.1\0"
    interp_offset = e_phoff + phentsize * phnum

    if capacity == 1:
        # 32-bit p_fmt field order: type, offset, vaddr, paddr, filesz, memsz, flags, align
        p_entry = struct.pack(
            p_fmt,
            3,                 # p_type = PT_INTERP
            interp_offset,     # p_offset
            1111,              # p_vaddr
            2222,              # p_paddr
            len(interp),       # p_filesz
            len(interp) + 9,   # p_memsz (deliberately different from filesz)
            0,                 # p_flags
            0,                 # p_align
        )
    else:
        # 64-bit p_fmt field order: type, flags, offset, vaddr, paddr, filesz, memsz, align
        p_entry = struct.pack(
            p_fmt,
            3,                 # p_type = PT_INTERP
            0,                 # p_flags
            interp_offset,     # p_offset
            1111,              # p_vaddr
            2222,              # p_paddr
            len(interp),       # p_filesz
            len(interp) + 9,   # p_memsz (deliberately different from filesz)
            0,                 # p_align
        )

    e_header = struct.pack(
        e_fmt,
        2,          # e_type
        machine,    # e_machine
        1,          # e_version
        0,          # e_entry
        e_phoff,    # e_phoff
        0,          # e_shoff
        flags,      # e_flags
        ehsize,     # e_ehsize
        phentsize,  # e_phentsize
        phnum,      # e_phnum
    )

    data = ident + e_header + p_entry + interp
    expected_interp = interp.rstrip(b"\0").decode("ascii")
    return data, expected_interp


COMBOS = [
    (1, 1, "<HHIIIIIHHH", "<IIIIIIII"),
    (1, 2, ">HHIIIIIHHH", ">IIIIIIII"),
    (2, 1, "<HHIQQQIHHH", "<IIQQQQQQ"),
    (2, 2, ">HHIQQQIHHH", ">IIQQQQQQ"),
]

# Chosen so that a naive signed ("h"/"i"/"q") reinterpretation of the fields
# would produce a different (wrong) value than the correct unsigned reading.
MACHINE_VALUE = 40000  # > 32767, so H vs h differ
FLAGS_VALUE = 0xFEDCBA98  # > 2**31-1, so I vs i differ


@pytest.mark.parametrize("capacity,encoding,e_fmt,p_fmt", COMBOS)
def test_elffile_parses_all_capacity_encoding_combinations(
    capacity, encoding, e_fmt, p_fmt
):
    data, expected_interp = _build_elf(
        capacity, encoding, e_fmt, p_fmt, MACHINE_VALUE, FLAGS_VALUE
    )
    ef = ELFFile(io.BytesIO(data))

    assert ef.capacity == capacity
    assert ef.encoding == encoding
    assert ef.machine == MACHINE_VALUE
    assert ef.flags == FLAGS_VALUE
    assert ef.interpreter == expected_interp


def test_invalid_magic_raises_with_expected_message():
    magic = b"XELF"
    ident = magic + bytes([1, 1]) + b"\x00" * 10
    assert len(ident) == 16

    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(ident))

    expected_message = f"invalid magic: {magic!r}"
    assert str(excinfo.value) == expected_message


def test_truncated_identification_raises_with_expected_message():
    # Far fewer than the 16 bytes required for the identification block.
    data = b"\x7fEL"

    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(data))

    assert str(excinfo.value) == "unable to parse identification"


def test_unrecognized_capacity_encoding_raises_with_expected_message():
    capacity, encoding = 9, 9
    ident = b"\x7fELF" + bytes([capacity, encoding]) + b"\x00" * 10
    assert len(ident) == 16

    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(ident))

    expected_message = (
        f"unrecognized capacity ({capacity}) or encoding ({encoding})"
    )
    assert str(excinfo.value) == expected_message


def test_truncated_machine_section_raises_with_expected_message():
    # Valid identification, but not enough bytes afterwards to read the
    # rest of the ELF header.
    ident = b"\x7fELF" + bytes([1, 1]) + b"\x00" * 10
    assert len(ident) == 16
    data = ident + b"\x00" * 5  # far short of calcsize("<HHIIIIIHHH") == 30

    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(data))

    assert str(excinfo.value) == "unable to parse machine and section information"
