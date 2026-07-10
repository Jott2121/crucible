import io
import struct
import pytest
from packaging._elffile import ELFFile, ELFInvalid

def _elf32(encoding, *, machine=3, flags=0, program_fields=None):
    endian = '<' if encoding == 1 else '>'
    phoff = 52
    path_offset = 200
    path = b'/expected-loader\x00'
    header = struct.pack(endian + 'HHIIIIIHHH', 0, machine, 1, 0, phoff, 0, flags, 52, 32, 1)
    if program_fields is None:
        program_fields = (3, path_offset, 180, 170, len(path), 1, 1, 1)
    data = bytearray(b'\x7fELF' + bytes((1, encoding)) + b'\x00' * 10 + header)
    data.extend(struct.pack(endian + 'IIIIIIII', *program_fields))
    data.extend(b'\x00' * (path_offset - len(data)))
    data.extend(path)
    return io.BytesIO(data)

def _elf64(encoding, *, machine=62, flags=0, program_fields=None):
    endian = '<' if encoding == 1 else '>'
    phoff = 64
    path_offset = 240
    path = b'/expected-loader\x00'
    header = struct.pack(endian + 'HHIQQQIHHH', 0, machine, 1, 0, phoff, 0, flags, 64, 56, 1)
    if program_fields is None:
        program_fields = (3, 7, path_offset, 180, 170, len(path), 1, 1)
    data = bytearray(b'\x7fELF' + bytes((2, encoding)) + b'\x00' * 10 + header)
    data.extend(struct.pack(endian + 'IIQQQQQQ', *program_fields))
    data.extend(b'\x00' * (path_offset - len(data)))
    data.extend(path)
    return io.BytesIO(data)

@pytest.mark.parametrize('stream_factory', [lambda: _elf32(1, machine=65535, flags=2147483648), lambda: _elf32(2, machine=65535, flags=2147483648), lambda: _elf64(1, machine=65535, flags=2147483648), lambda: _elf64(2, machine=65535, flags=2147483648)])
def test_header_machine_and_flags_are_unsigned(stream_factory):
    elf = ELFFile(stream_factory())
    assert elf.machine == 65535
    assert elf.flags == 2147483648

class _RecordingBytesIO(io.BytesIO):

    def __init__(self, initial_bytes):
        super().__init__(initial_bytes)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)

def test_invalid_magic_reports_the_actual_magic_bytes():
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(b'NOPE' + b'\x00' * 12))
    assert str(exc_info.value) == "invalid magic: b'NOPE'"

def test_short_identification_has_a_specific_error_message():
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(b'\x7fELF'))
    assert str(exc_info.value) == 'unable to parse identification'

def test_unknown_capacity_or_encoding_has_a_specific_error_message():
    ident = b'\x7fELF' + bytes((9, 1)) + b'\x00' * 10
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(ident))
    assert str(exc_info.value) == 'unrecognized capacity (9) or encoding (1)'

def test_short_elf_header_has_a_specific_error_message():
    ident = b'\x7fELF' + bytes((1, 1)) + b'\x00' * 10
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(ident))
    assert str(exc_info.value) == 'unable to parse machine and section information'

def test_identification_is_read_as_unsigned_bytes():

    class TrackingELFFile(ELFFile):

        def __init__(self, source):
            self.formats = []
            super().__init__(source)

        def _read(self, fmt):
            self.formats.append(fmt)
            return super()._read(fmt)
    elf = TrackingELFFile(_elf32(1))
    assert elf.formats[0] == '16B'
