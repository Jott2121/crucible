import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


def make_elf(
    capacity,
    encoding,
    *,
    machine=62,
    flags=0x12345678,
    program_type=3,
    program_offset=256,
    program_vaddr=400,
    program_filesz=8,
    program_memsz=1,
    payload=b"/interp\0",
):
    byteorder = "<" if encoding == 1 else ">"

    ident = b"\x7fELF" + bytes([capacity, encoding]) + b"\0" * 10
    phoff = 128

    if capacity == 1:
        header = struct.pack(
            byteorder + "HHIIIIIHHH",
            2,
            machine,
            1,
            0,
            phoff,
            0,
            flags,
            52,
            32,
            1,
        )
        program_header = struct.pack(
            byteorder + "IIIIIIII",
            program_type,
            program_offset,
            program_vaddr,
            0,
            program_filesz,
            program_memsz,
            0,
            0,
        )
    else:
        header = struct.pack(
            byteorder + "HHIQQQIHHH",
            2,
            machine,
            1,
            0,
            phoff,
            0,
            flags,
            64,
            56,
            1,
        )
        program_header = struct.pack(
            byteorder + "IIQQQQQQ",
            program_type,
            0,
            program_offset,
            program_vaddr,
            0,
            program_filesz,
            program_memsz,
            0,
        )

    data = bytearray(512)
    data[:16] = ident
    data[16 : 16 + len(header)] = header
    data[phoff : phoff + len(program_header)] = program_header
    data[256 : 256 + len(payload)] = payload
    return io.BytesIO(data)


@pytest.mark.parametrize("capacity,encoding", [(1, 1), (1, 2), (2, 1), (2, 2)])
def test_parses_each_elf_layout_and_uses_the_interpreter_file_size(capacity, encoding):
    elf = ELFFile(make_elf(capacity, encoding))

    assert elf.capacity == capacity
    assert elf.encoding == encoding
    assert elf.machine == 62
    assert elf.flags == 0x12345678
    assert elf.interpreter == "/interp"


@pytest.mark.parametrize("capacity,encoding", [(1, 1), (1, 2), (2, 1), (2, 2)])
def test_unsigned_machine_field_preserves_high_bit_values(capacity, encoding):
    elf = ELFFile(make_elf(capacity, encoding, machine=0xFFFF))

    assert elf.machine == 0xFFFF


@pytest.mark.parametrize("capacity,encoding", [(1, 1), (1, 2), (2, 1), (2, 2)])
def test_unsigned_program_offsets_do_not_become_negative(capacity, encoding):
    elf = ELFFile(
        make_elf(
            capacity,
            encoding,
            program_offset=0x80000000,
            program_filesz=1,
            payload=b"x",
        )
    )

    # A PT_INTERP header whose unsigned offset is beyond EOF has an empty
    # interpreter string; it must not be treated as a negative offset.
    assert elf.interpreter == ""


def test_invalid_magic_reports_the_actual_magic():
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(b"NOPE" + b"\0" * 12))

    assert str(exc_info.value) == "invalid magic: b'NOPE'"


def test_short_identification_has_a_specific_error_message():
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(b"\x7fELF"))

    assert str(exc_info.value) == "unable to parse identification"


def test_short_elf_header_has_a_specific_error_message():
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(b"\x7fELF" + bytes([1, 1]) + b"\0" * 10))

    assert str(exc_info.value) == "unable to parse machine and section information"


def test_unknown_capacity_or_encoding_reports_the_values():
    data = b"\x7fELF" + bytes([9, 1]) + b"\0" * 10

    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(data))

    assert str(exc_info.value) == "unrecognized capacity (9) or encoding (1)"
