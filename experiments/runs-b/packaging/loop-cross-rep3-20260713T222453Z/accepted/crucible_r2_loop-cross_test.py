import io
import struct

from packaging._elffile import ELFFile


def _elf_bytes(bits, encoding, program_header, payload=b"", payload_offset=256):
    if bits == 1:
        endian = "<" if encoding == 1 else ">"
        header_format = endian + "HHIIIIIHHH"
        program_format = endian + "IIIIIIII"
        header_values = (2, 3, 1, 0, 128, 0, 0, 52, 32, 1)
    else:
        endian = "<" if encoding == 1 else ">"
        header_format = endian + "HHIQQQIHHH"
        program_format = endian + "IIQQQQQQ"
        header_values = (2, 62, 1, 0, 128, 0, 0, 64, 56, 1)

    program_size = struct.calcsize(program_format)
    contents = bytearray(max(128 + program_size, payload_offset + len(payload)))
    contents[:16] = b"\x7fELF" + bytes([bits, encoding]) + b"\0" * 10
    struct.pack_into(header_format, contents, 16, *header_values)
    struct.pack_into(program_format, contents, 128, *program_header)
    contents[payload_offset : payload_offset + len(payload)] = payload
    return bytes(contents)


def test_32_bit_big_endian_interpreter_uses_type_offset_and_filesize_fields():
    payload = b"/loader\0"
    data = bytearray(
        _elf_bytes(
            1,
            2,
            # type, offset, vaddr, paddr, filesz, memsz, flags, align
            (3, 256, 300, 0, len(payload), 1, 0, 0),
            payload,
        )
    )
    data[300:306] = b"other\0"

    elf = ELFFile(io.BytesIO(data))

    assert elf.interpreter == "/loader"


def test_64_bit_little_endian_interpreter_uses_type_offset_and_filesize_fields():
    payload = b"/loader\0"
    data = bytearray(
        _elf_bytes(
            2,
            1,
            # type, flags, offset, vaddr, paddr, filesz, memsz, align
            (3, 0, 256, 300, 0, len(payload), 1, 0),
            payload,
        )
    )
    data[300:306] = b"other\0"

    elf = ELFFile(io.BytesIO(data))

    assert elf.interpreter == "/loader"


class _HugeReadStream(io.BytesIO):
    def __init__(self, contents, huge_size):
        super().__init__(contents)
        self._huge_size = huge_size

    def read(self, size=-1):
        if size == self._huge_size:
            return b"/loader\0"
        return super().read(size)


def test_interpreter_filesize_is_unsigned_for_all_elf_layouts():
    for bits, encoding in ((1, 1), (1, 2), (2, 1), (2, 2)):
        huge_size = 1 << (31 if bits == 1 else 63)
        if bits == 1:
            program_header = (3, 256, 0, 0, huge_size, 0, 0, 0)
        else:
            program_header = (3, 0, 256, 0, 0, huge_size, 0, 0)

        contents = _elf_bytes(
            bits,
            encoding,
            program_header,
            b"/loader\0trailing-data",
        )
        elf = ELFFile(_HugeReadStream(contents, huge_size))

        assert elf.interpreter == "/loader"
