import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


class _SparseELF:
    def __init__(self, base: bytes, segment_offset: int, segment: bytes) -> None:
        self._base = base
        self._segment_offset = segment_offset
        self._segment = segment
        self._position = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence != 0:
            raise ValueError("only absolute seeks are supported")
        if offset < 0:
            raise ValueError("negative seek position")
        self._position = offset
        return offset

    def read(self, size: int = -1) -> bytes:
        if self._position < len(self._base):
            data = self._base[self._position :]
        elif self._position == self._segment_offset:
            data = self._segment
        else:
            data = b""

        if size >= 0:
            data = data[:size]
        self._position += len(data)
        return data


def test_invalid_magic_with_high_bit_is_reported_as_elf_invalid() -> None:
    invalid_identification = b"\xffELF" + bytes([2, 1]) + b"\0" * 10

    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(_SparseELF(invalid_identification, 0, b""))

    assert str(exc_info.value) == "invalid magic: b'\\xffELF'"


@pytest.mark.parametrize(
    ("encoding", "endian"),
    [
        (1, "<"),
        (2, ">"),
    ],
)
def test_64_bit_interpreter_offset_is_an_unsigned_integer(
    encoding: int, endian: str
) -> None:
    program_header_offset = 0x100
    interpreter_offset = 1 << 63
    interpreter = b"/lib64/ld-test.so\0"

    ident = b"\x7fELF" + bytes([2, encoding]) + b"\0" * 10
    elf_header = struct.pack(
        f"{endian}HHIQQQIHHH",
        2,
        62,
        1,
        0,
        program_header_offset,
        0,
        0,
        64,
        56,
        1,
    )
    program_header = struct.pack(
        f"{endian}IIQQQQQQ",
        3,
        0,
        interpreter_offset,
        0,
        0,
        len(interpreter),
        len(interpreter),
        1,
    )
    base = (ident + elf_header).ljust(program_header_offset, b"\0") + program_header

    elf = ELFFile(_SparseELF(base, interpreter_offset, interpreter))

    assert elf.interpreter == "/lib64/ld-test.so"
