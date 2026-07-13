import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# The *correct* (unmutated) format strings used by ELFFile for each
# (capacity, encoding) combination.  These are used here only to construct
# valid-looking ELF byte streams; the module under test uses its own
# internal (possibly mutated) copies to parse them.
FORMATS = {
    (1, 1): ("<HHIIIIIHHH", "<IIIIIIII"),
    (1, 2): (">HHIIIIIHHH", ">IIIIIIII"),
    (2, 1): ("<HHIQQQIHHH", "<IIQQQQQQ"),
    (2, 2): (">HHIQQQIHHH", ">IIQQQQQQ"),
}


def build_elf(capacity: int, encoding: int, offset_value: int) -> bytes:
    """Construct minimal ELF bytes with a single PT_INTERP program header
    whose p_offset field is `offset_value` (expected to be read as an
    *unsigned* integer by correct code)."""
    e_fmt, p_fmt = FORMATS[(capacity, encoding)]

    ident = bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding, 1, 0, 0]) + b"\x00" * 7

    e_header_size = struct.calcsize(e_fmt)
    p_header_size = struct.calcsize(p_fmt)
    e_phoff = 16 + e_header_size
    e_phnum = 1

    e_header = struct.pack(
        e_fmt,
        0,  # e_type
        0,  # e_machine
        0,  # e_version
        0,  # e_entry
        e_phoff,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        e_phoff,  # e_ehsize (unused by ELFFile)
        p_header_size,  # e_phentsize
        e_phnum,  # e_phnum
    )

    if capacity == 1:
        # 32-bit layout: p_type, p_offset, p_vaddr, p_paddr, p_filesz,
        # p_memsz, p_flags, p_align
        p_header = struct.pack(p_fmt, 3, offset_value, 0, 0, 5, 0, 0, 0)
    else:
        # 64-bit layout: p_type, p_flags, p_offset, p_vaddr, p_paddr,
        # p_filesz, p_memsz, p_align
        p_header = struct.pack(p_fmt, 3, 0, offset_value, 0, 0, 5, 0, 0)

    return ident + e_header + p_header


class RecordingBytesIO(io.BytesIO):
    """A BytesIO subclass that records every offset passed to seek(),
    tolerating offsets too large for the real implementation."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.seek_calls: list[int] = []

    def seek(self, offset, whence=0):  # type: ignore[override]
        self.seek_calls.append(offset)
        try:
            return super().seek(offset, whence)
        except OverflowError:
            return self.tell()


def _assert_offset_parsed_unsigned(capacity: int, encoding: int, offset_value: int) -> None:
    data = build_elf(capacity, encoding, offset_value)
    f = RecordingBytesIO(data)
    elf = ELFFile(f)
    # Access the property; we don't care about the returned string, only
    # about what offset was actually requested via seek().
    elf.interpreter
    assert f.seek_calls, "interpreter property never attempted to seek"
    assert f.seek_calls[-1] == offset_value


# ---------------------------------------------------------------------------
# Tests targeting p_fmt sign mutants (32-bit LSB/MSB, 64-bit LSB/MSB)
# ---------------------------------------------------------------------------


def test_program_header_offset_32bit_lsb_is_unsigned():
    # 2**31 has the top bit of a 4-byte field set; a signed reading would
    # turn this into a negative number.
    _assert_offset_parsed_unsigned(1, 1, 0x80000000)


def test_program_header_offset_32bit_msb_is_unsigned():
    _assert_offset_parsed_unsigned(1, 2, 0x80000000)


def test_program_header_offset_64bit_lsb_is_unsigned():
    # 2**63 has the top bit of an 8-byte field set; a signed reading would
    # turn this into a negative number.
    _assert_offset_parsed_unsigned(2, 1, 2**63)


def test_program_header_offset_64bit_msb_is_unsigned():
    _assert_offset_parsed_unsigned(2, 2, 2**63)


# ---------------------------------------------------------------------------
# Tests targeting the ident-parsing format ("16B" vs "16b")
# ---------------------------------------------------------------------------


def test_capacity_is_parsed_as_unsigned_byte():
    # capacity byte 0x81 == 129 as unsigned, but -127 as signed (two's
    # complement, 8-bit). Neither (129, 1) nor (-127, 1) exist in the
    # capacity/encoding dispatch table, so ELFInvalid is raised, and its
    # message should report the *unsigned* value if ident bytes are parsed
    # correctly with "16B".
    capacity = 0x81  # 129 unsigned / -127 signed
    encoding = 1
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding, 1, 0, 0]) + b"\x00" * 7

    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(ident))

    message = str(excinfo.value)
    assert "129" in message
    assert "-127" not in message


# ---------------------------------------------------------------------------
# Tests targeting the exact error messages
# ---------------------------------------------------------------------------


def test_truncated_ident_error_message():
    # Fewer than 16 bytes available -> struct.error while reading ident.
    truncated = bytes([0x7F, 0x45, 0x4C, 0x46, 1])
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(truncated))
    assert str(excinfo.value) == "unable to parse identification"


def test_truncated_machine_section_error_message():
    # Valid 16-byte ident, but nothing after it -> struct.error while
    # reading the e_fmt header fields.
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, 1, 1, 1, 0, 0]) + b"\x00" * 7
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(ident))
    assert str(excinfo.value) == "unable to parse machine and section information"
