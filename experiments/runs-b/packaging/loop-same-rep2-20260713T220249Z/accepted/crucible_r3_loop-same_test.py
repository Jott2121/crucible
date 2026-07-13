import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


def _build_64bit_elf(endian: str, encoding_byte: int, offset_value: int) -> bytes:
    """
    Build a minimal 64-bit ELF blob (LSB or MSB depending on `endian`/
    `encoding_byte`) containing a single PT_INTERP program header whose
    p_offset field encodes `offset_value` (interpreted as an *unsigned*
    64-bit integer, per the ELF spec and the original ``_p_fmt``).
    """
    ident = b"\x7fELF" + bytes([2, encoding_byte]) + bytes(10)  # capacity=2 (C64)

    e_fmt = f"{endian}HHIQQQIHHH"
    p_fmt = f"{endian}IIQQQQQQ"

    header_len = 16 + struct.calcsize(e_fmt)
    p_entry_len = struct.calcsize(p_fmt)

    e_header = struct.pack(
        e_fmt,
        0,  # e_type
        62,  # e_machine
        0,  # e_version
        0,  # e_entry
        header_len,  # e_phoff -- program header starts right after this header
        0,  # e_shoff
        0,  # e_flags
        0,  # e_ehsize
        p_entry_len,  # e_phentsize
        1,  # e_phnum
    )

    ph_entry = struct.pack(
        p_fmt,
        3,  # p_type == PT_INTERP
        0,  # p_flags
        offset_value,  # p_offset (unsigned interpretation)
        0,  # p_vaddr
        0,  # p_paddr
        0,  # p_filesz
        0,  # p_memsz
        0,  # p_align
    )

    return ident + e_header + ph_entry


def test_capacity_and_encoding_are_read_as_unsigned_bytes():
    # Kills mutant that reads ident with "16b" (signed bytes) instead of
    # "16B" (unsigned bytes). Using a deliberately invalid capacity value
    # of 200 lets us observe how that byte was interpreted: unsigned
    # gives 200, signed gives 200 - 256 == -56.
    data = b"\x7fELF" + bytes([200, 1]) + bytes(10)  # 16 bytes total ident
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(data))
    message = str(exc_info.value)
    assert "200" in message
    assert "-56" not in message


def test_64bit_lsb_program_header_offset_read_as_unsigned():
    # Kills mutant that changes the 64-bit LSB p_fmt from
    # "<IIQQQQQQ" (unsigned) to "<iiqqqqqq" (signed).
    #
    # We encode p_offset's raw bytes to represent 2**63 + 5. Interpreted
    # as *unsigned* (correct behavior), this value is far larger than
    # Py_ssize_t's max and causes an OverflowError when passed to
    # `seek()`. Interpreted as *signed* (mutant behavior), the same bytes
    # decode to a large-but-in-range negative number, causing a
    # ValueError (negative seek) instead -- a different exception type.
    offset_value = 2**63 + 5
    data = _build_64bit_elf(endian="<", encoding_byte=1, offset_value=offset_value)

    elf = ELFFile(io.BytesIO(data))
    with pytest.raises(OverflowError):
        elf.interpreter


def test_64bit_msb_program_header_offset_read_as_unsigned():
    # Kills mutant that changes the 64-bit MSB p_fmt from
    # ">IIQQQQQQ" (unsigned) to ">iiqqqqqq" (signed). Same reasoning as
    # the LSB test above, but for big-endian encoding.
    offset_value = 2**63 + 5
    data = _build_64bit_elf(endian=">", encoding_byte=2, offset_value=offset_value)

    elf = ELFFile(io.BytesIO(data))
    with pytest.raises(OverflowError):
        elf.interpreter
