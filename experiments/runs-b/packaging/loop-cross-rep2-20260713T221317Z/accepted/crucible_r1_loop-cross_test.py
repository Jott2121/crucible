import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


class SparseBytes:
    def __init__(self) -> None:
        self.position = 0
        self._bytes: dict[int, int] = {}

    def put(self, offset: int, data: bytes) -> None:
        self._bytes.update(enumerate(data, offset))

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self.position = offset
        elif whence == 1:
            self.position += offset
        else:
            raise ValueError("unsupported seek mode")
        return self.position

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = 0
        result = bytes(self._bytes.get(self.position + index, 0) for index in range(size))
        self.position += size
        return result


def make_elf(capacity: int, encoding: int) -> SparseBytes:
    little_endian = encoding == 1
    prefix = "<" if little_endian else ">"

    f = SparseBytes()
    f.put(0, b"\x7fELF" + bytes((capacity, encoding)) + b"\0" * 10)

    if capacity == 1:
        phoff = 0x80001000
        p_offset = 0x80002000
        alternate_offset = 0x80003000
        header = struct.pack(
            prefix + "HHIIIIIHHH",
            2,
            62,
            1,
            0,
            phoff,
            0,
            0,
            52,
            32,
            1,
        )
        program_header = struct.pack(
            prefix + "IIIIIIII",
            3,
            p_offset,
            alternate_offset,
            0,
            3,
            9,
            0,
            0,
        )
    else:
        phoff = 0x8000000000001000
        p_offset = 0x8000000000002000
        alternate_offset = 0x8000000000003000
        header = struct.pack(
            prefix + "HHIQQQIHHH",
            2,
            62,
            1,
            0,
            phoff,
            0,
            0,
            64,
            56,
            1,
        )
        program_header = struct.pack(
            prefix + "IIQQQQQQ",
            3,
            4,
            p_offset,
            alternate_offset,
            0,
            3,
            9,
            0,
        )

    f.put(16, header)
    f.put(phoff, program_header)
    f.put(p_offset, b"ok\0EXTRA")
    f.put(alternate_offset, b"wrong\0")
    return f


@pytest.mark.parametrize(
    ("capacity", "encoding"),
    [(1, 1), (1, 2), (2, 1), (2, 2)],
)
def test_parses_all_supported_elf_layouts_and_finds_interpreter(
    capacity: int, encoding: int
) -> None:
    elf = ELFFile(make_elf(capacity, encoding))

    assert elf.capacity == capacity
    assert elf.encoding == encoding
    assert elf.machine == 62
    assert elf.interpreter == "ok"


def test_valid_elf_magic_is_accepted() -> None:
    elf = ELFFile(make_elf(1, 1))

    assert elf.interpreter == "ok"


def test_truncated_identification_has_documented_error_message() -> None:
    with pytest.raises(ELFInvalid) as error:
        ELFFile(io.BytesIO(b"\x7fELF"))

    assert str(error.value) == "unable to parse identification"


def test_truncated_elf_header_has_documented_error_message() -> None:
    incomplete = b"\x7fELF" + bytes((1, 1)) + b"\0" * 10

    with pytest.raises(ELFInvalid) as error:
        ELFFile(io.BytesIO(incomplete))

    assert str(error.value) == "unable to parse machine and section information"


def test_identification_is_read_as_unsigned_bytes() -> None:
    class RecordingELFFile(ELFFile):
        def __init__(self) -> None:
            self.formats: list[str] = []
            super().__init__(io.BytesIO())

        def _read(self, fmt: str) -> tuple[int, ...]:
            self.formats.append(fmt)
            if len(self.formats) == 1:
                return tuple(b"\x7fELF" + bytes((1, 1)) + b"\0" * 10)
            return (2, 62, 1, 0, 0, 0, 0, 52, 32, 0)

    elf = RecordingELFFile()

    assert elf.formats[0] == "16B"
    assert elf.machine == 62
