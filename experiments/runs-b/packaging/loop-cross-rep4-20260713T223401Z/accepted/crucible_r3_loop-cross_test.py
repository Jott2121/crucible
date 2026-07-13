import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


def _elf_with_interpreter(capacity: int, encoding: int) -> tuple[bytes, str, int, int]:
    endian = "<" if encoding == 1 else ">"
    program_offset = 128
    interpreter_offset = 300
    decoy_offset = 320
    interpreter_bytes = b"/lib/target\x00"
    expected_interpreter = "/lib/target"

    ident = bytearray(b"\x7fELF")
    ident.extend((capacity, encoding, 1, 0))
    ident.extend(b"\x00" * 8)

    if capacity == 1:
        header_format = endian + "HHIIIIIHHH"
        program_format = endian + "IIIIIIII"
        header = struct.pack(
            header_format,
            2,
            62,
            1,
            0,
            program_offset,
            0,
            0,
            52,
            struct.calcsize(program_format),
            1,
        )
        program_header = struct.pack(
            program_format,
            3,
            interpreter_offset,
            decoy_offset,
            333,
            len(interpreter_bytes),
            5,
            0,
            0xFFFFFFFF,
        )
        unsigned_last_field = 0xFFFFFFFF
    else:
        header_format = endian + "HHIQQQIHHH"
        program_format = endian + "IIQQQQQQ"
        header = struct.pack(
            header_format,
            2,
            62,
            1,
            0,
            program_offset,
            0,
            0,
            64,
            struct.calcsize(program_format),
            1,
        )
        program_header = struct.pack(
            program_format,
            3,
            0xFFFFFFFF,
            interpreter_offset,
            decoy_offset,
            333,
            len(interpreter_bytes),
            5,
            0xFFFFFFFFFFFFFFFF,
        )
        unsigned_last_field = 0xFFFFFFFFFFFFFFFF

    data = bytearray(400)
    data[:16] = ident
    data[16 : 16 + len(header)] = header
    data[program_offset : program_offset + len(program_header)] = program_header
    data[interpreter_offset : interpreter_offset + len(interpreter_bytes)] = interpreter_bytes
    data[decoy_offset : decoy_offset + 20] = b"/not-the-interpreter\x00"

    return bytes(data), expected_interpreter, program_offset, unsigned_last_field


@pytest.mark.parametrize(
    ("capacity", "encoding"),
    [(1, 1), (1, 2), (2, 1), (2, 2)],
)
def test_parses_each_elf_layout_using_unsigned_program_header_fields(
    capacity: int, encoding: int
) -> None:
    data, expected_interpreter, program_offset, unsigned_last_field = (
        _elf_with_interpreter(capacity, encoding)
    )

    elf = ELFFile(io.BytesIO(data))

    assert elf.capacity == capacity
    assert elf.encoding == encoding
    assert elf.interpreter == expected_interpreter

    elf._f.seek(program_offset)
    program_fields = elf._read(elf._p_fmt)
    assert program_fields[-1] == unsigned_last_field


def test_invalid_magic_is_reported_as_elf_invalid_even_when_a_magic_byte_is_high() -> None:
    invalid_ident = b"\xffELF" + bytes((1, 1, 1, 0)) + b"\x00" * 8

    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(invalid_ident))
