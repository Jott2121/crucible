import io
import struct

import pytest

from packaging._elffile import ELFFile


def _build_ident(capacity: int, encoding: int) -> bytes:
    return bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding] + [0] * 10)


def _e_fmt(byteorder: str, is64: bool) -> str:
    return byteorder + ("HHIQQQIHHH" if is64 else "HHIIIIIHHH")


def _p_fmt(byteorder: str, is64: bool) -> str:
    return byteorder + ("IIQQQQQQ" if is64 else "IIIIIIII")


def build_elf(capacity: int, encoding: int, offset: int, filesz: int) -> bytes:
    """
    Build a minimal ELF file (header + one PT_INTERP program header) with the
    given capacity/encoding, and the given (possibly huge) offset/filesz
    values stored in the program header.
    """
    is64 = capacity == 2
    byteorder = "<" if encoding == 1 else ">"

    ident = _build_ident(capacity, encoding)
    e_fmt = _e_fmt(byteorder, is64)
    p_fmt = _p_fmt(byteorder, is64)

    phentsize = struct.calcsize(p_fmt)
    ehsize = struct.calcsize(e_fmt)
    phoff = len(ident) + ehsize

    # e_type, machine, version, entry, phoff, shoff, flags, ehsize,
    # phentsize, phnum
    e_header = struct.pack(e_fmt, 0, 0, 0, 0, phoff, 0, 0, 0, phentsize, 1)

    if is64:
        # type, flags, offset, vaddr, paddr, filesz, memsz, align
        p_header = struct.pack(p_fmt, 3, 0, offset, 0, 0, filesz, 0, 0)
    else:
        # type, offset, vaddr, paddr, filesz, memsz, flags, align
        p_header = struct.pack(p_fmt, 3, offset, 0, 0, filesz, 0, 0, 0)

    return ident + e_header + p_header


@pytest.mark.parametrize("capacity,encoding", [(1, 1), (1, 2), (2, 1), (2, 2)])
def test_program_header_large_offset_and_filesz_parsed_as_unsigned(
    capacity, encoding
):
    """
    The program header fields (offset/filesz) must be parsed as *unsigned*
    integers. Mutants that change the program header format characters from
    upper-case (I/Q, unsigned) to lower-case (i/q, signed) will misinterpret
    values whose top bit is set as negative numbers.
    """
    if capacity == 2:
        offset = (1 << 63) + 5
        filesz = (1 << 63) + 7
    else:
        offset = (1 << 31) + 5
        filesz = (1 << 31) + 7

    data_bytes = build_elf(capacity, encoding, offset, filesz)
    f = io.BytesIO(data_bytes)
    elf = ELFFile(f)

    f.seek(elf._e_phoff)
    data = elf._read(elf._p_fmt)

    type_idx, offset_idx, filesz_idx = elf._p_idx

    assert data[type_idx] == 3
    assert data[offset_idx] == offset
    assert data[filesz_idx] == filesz


def test_interpreter_reads_expected_path_64bit_lsb():
    """
    Sanity/regression check that a well-formed 64-bit little-endian ELF file
    with a PT_INTERP program header is parsed correctly end-to-end.
    """
    interp = b"/lib64/ld-linux-x86-64.so.2\0"
    capacity, encoding = 2, 1
    byteorder = "<"

    ident = _build_ident(capacity, encoding)
    e_fmt = _e_fmt(byteorder, True)
    p_fmt = _p_fmt(byteorder, True)

    ehsize = struct.calcsize(e_fmt)
    phentsize = struct.calcsize(p_fmt)
    phoff = len(ident) + ehsize
    interp_offset = phoff + phentsize

    e_header = struct.pack(e_fmt, 0, 0, 0, 0, phoff, 0, 0, 0, phentsize, 1)
    p_header = struct.pack(
        p_fmt, 3, 0, interp_offset, 0, 0, len(interp), 0, 0
    )

    data_bytes = ident + e_header + p_header + interp
    f = io.BytesIO(data_bytes)
    elf = ELFFile(f)

    assert elf.interpreter == "/lib64/ld-linux-x86-64.so.2"


def test_program_header_small_offset_and_filesz_roundtrip():
    """
    For a small (well within positive-signed range) offset/filesz, values
    should round-trip exactly regardless of capacity/encoding -- this
    complements the large-value test by confirming ordinary usage keeps
    working.
    """
    for capacity, encoding in [(1, 1), (1, 2), (2, 1), (2, 2)]:
        offset = 123
        filesz = 45
        data_bytes = build_elf(capacity, encoding, offset, filesz)
        f = io.BytesIO(data_bytes)
        elf = ELFFile(f)

        f.seek(elf._e_phoff)
        data = elf._read(elf._p_fmt)
        type_idx, offset_idx, filesz_idx = elf._p_idx

        assert data[type_idx] == 3
        assert data[offset_idx] == offset
        assert data[filesz_idx] == filesz
