import struct
from io import BytesIO

import pytest

from packaging._elffile import ELFFile


def _pack_ident(capacity: int, encoding: int) -> bytes:
    ident = bytearray(16)
    ident[0:4] = b"\x7fELF"
    ident[4] = capacity
    ident[5] = encoding
    return bytes(ident)


@pytest.mark.parametrize(
    ("capacity", "encoding"),
    [(1, 1), (1, 2), (2, 1), (2, 2)],
)
def test_elf_header_flags_field_is_parsed_as_unsigned(capacity, encoding):
    """e_flags must be read as an unsigned 32-bit integer.

    If the format string were mistakenly changed to use signed integers,
    a value with the top bit set (0xFFFFFFFF) would come back as -1
    instead of 4294967295.
    """
    endian = "<" if encoding == 1 else ">"
    if capacity == 1:
        e_fmt = endian + "HHIIIIIHHH"
    else:
        e_fmt = endian + "HHIQQQIHHH"

    flags_value = 0xFFFFFFFF  # max uint32; becomes -1 if read as signed int32.

    header = struct.pack(
        e_fmt,
        2,  # e_type
        3,  # e_machine
        1,  # e_version
        0,  # e_entry
        0,  # e_phoff
        0,  # e_shoff
        flags_value,  # e_flags
        0,  # e_ehsize
        0,  # e_phentsize
        0,  # e_phnum -- no program headers, so interpreter parsing is skipped
    )
    data = _pack_ident(capacity, encoding) + header
    elf = ELFFile(BytesIO(data))

    assert elf.flags == 4294967295


@pytest.mark.parametrize("encoding", [1, 2])
def test_program_header_offset_is_parsed_as_unsigned_32bit(encoding):
    """p_offset (32-bit ELF) must be read as an unsigned integer.

    A p_offset with the top bit set (2**31) is a large positive seek
    target when read correctly (unsigned). If it were read as a signed
    32-bit integer instead, it would become negative, and seeking to a
    negative position raises an error instead of succeeding.
    """
    capacity = 1
    endian = "<" if encoding == 1 else ">"
    e_fmt = endian + "HHIIIIIHHH"
    p_fmt = endian + "IIIIIIII"

    e_phentsize = struct.calcsize(p_fmt)
    ehdr_size = 16 + struct.calcsize(e_fmt)
    e_phoff = ehdr_size

    header = struct.pack(
        e_fmt,
        2,  # e_type
        3,  # e_machine
        1,  # e_version
        0,  # e_entry
        e_phoff,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        0,  # e_ehsize
        e_phentsize,  # e_phentsize
        1,  # e_phnum -- exactly one program header
    )

    huge_offset = 2**31  # becomes negative if read as a signed int32.
    p_header = struct.pack(
        p_fmt,
        3,  # p_type == PT_INTERP
        huge_offset,  # p_offset
        0,  # p_vaddr
        0,  # p_paddr
        4,  # p_filesz
        0,  # p_memsz
        0,  # p_flags
        0,  # p_align
    )

    data = _pack_ident(capacity, encoding) + header + p_header
    elf = ELFFile(BytesIO(data))

    # There is no actual data at the huge offset, so reading from there
    # should just yield an empty string rather than raising an error from
    # attempting to seek to a negative position.
    assert elf.interpreter == ""
