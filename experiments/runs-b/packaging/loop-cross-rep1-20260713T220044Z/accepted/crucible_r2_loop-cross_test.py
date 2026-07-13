import io
import struct

import pytest

from packaging._elffile import ELFFile


_INTERPRETER = b"/lib/ld-unit.so\0"


def _make_elf(capacity, encoding, declared_size=None):
    prefix = "<" if encoding == 1 else ">"

    if capacity == 1:
        header_format = prefix + "HHIIIIIHHH"
        program_format = prefix + "IIIIIIII"
        header_size = 52
        program_offset = 64
        program_size = 32
        interpreter_offset = 200
        alternate_offset = 240
        header = struct.pack(
            header_format,
            2,
            3,
            1,
            0,
            program_offset,
            0,
            0,
            header_size,
            program_size,
            1,
        )
        program = struct.pack(
            program_format,
            3,
            interpreter_offset,
            alternate_offset,
            0,
            len(_INTERPRETER) if declared_size is None else declared_size,
            2,
            0,
            0,
        )
    else:
        header_format = prefix + "HHIQQQIHHH"
        program_format = prefix + "IIQQQQQQ"
        header_size = 64
        program_offset = 128
        program_size = 56
        interpreter_offset = 300
        alternate_offset = 340
        header = struct.pack(
            header_format,
            2,
            62,
            1,
            0,
            program_offset,
            0,
            0,
            header_size,
            program_size,
            1,
        )
        program = struct.pack(
            program_format,
            3,
            0,
            interpreter_offset,
            alternate_offset,
            0,
            len(_INTERPRETER) if declared_size is None else declared_size,
            2,
            0,
        )

    include_alternate = declared_size is None
    end = interpreter_offset + len(_INTERPRETER)
    if include_alternate:
        end = max(end, alternate_offset + len(b"/wrong\0"))

    data = bytearray(end)
    data[:16] = b"\x7fELF" + bytes((capacity, encoding)) + b"\0" * 10
    data[16 : 16 + len(header)] = header
    data[program_offset : program_offset + len(program)] = program
    data[interpreter_offset : interpreter_offset + len(_INTERPRETER)] = _INTERPRETER

    if include_alternate:
        data[alternate_offset : alternate_offset + len(b"/wrong\0")] = b"/wrong\0"

    return bytes(data)


@pytest.mark.parametrize(
    ("capacity", "encoding"),
    [(1, 1), (1, 2), (2, 1), (2, 2)],
)
def test_interpreter_uses_the_correct_program_header_layout(capacity, encoding):
    elf = ELFFile(io.BytesIO(_make_elf(capacity, encoding)))

    assert elf.interpreter == "/lib/ld-unit.so"


class _ShortReadForLargeRequests(io.BytesIO):
    """A valid short-reading stream that distinguishes signed file sizes."""

    def read(self, size=-1):
        if size > 1_000_000:
            size = len(_INTERPRETER)
        return super().read(size)


@pytest.mark.parametrize(
    ("capacity", "encoding", "large_size"),
    [
        (1, 1, 1 << 31),
        (1, 2, 1 << 31),
        (2, 1, 1 << 63),
        (2, 2, 1 << 63),
    ],
)
def test_interpreter_file_size_is_an_unsigned_elf_field(
    capacity, encoding, large_size
):
    # The extra bytes are only returned by a negative-size read.  A correctly
    # decoded unsigned ELF p_filesz requests the positive large_size instead.
    blob = _make_elf(capacity, encoding, declared_size=large_size) + b"unexpected"
    elf = ELFFile(_ShortReadForLargeRequests(blob))

    assert elf.interpreter == "/lib/ld-unit.so"
