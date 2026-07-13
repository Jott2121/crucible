import io
import struct
import pytest
from packaging._elffile import ELFFile, ELFInvalid

def make_elf(capacity, encoding, *, machine=62, flags=0, interp='/chosen'):
    endian = '<' if encoding == 1 else '>'
    ident = b'\x7fELF' + bytes([capacity, encoding]) + b'\x00' * 10
    if capacity == 1:
        header_format = endian + 'HHIIIIIHHH'
        program_format = endian + 'IIIIIIII'
        phoff = 52
        phentsize = 32
        interp_offset = 160
        program = [3, interp_offset, 0, 0, len(interp) + 1, 0, 0, 0]
        header = struct.pack(header_format, 2, machine, 1, 0, phoff, 0, flags, 52, phentsize, 1)
    else:
        header_format = endian + 'HHIQQQIHHH'
        program_format = endian + 'IIQQQQQQ'
        phoff = 64
        phentsize = 56
        interp_offset = 192
        program = [3, 0, interp_offset, 0, 0, len(interp) + 1, 0, 0]
        header = struct.pack(header_format, 2, machine, 1, 0, phoff, 0, flags, 64, phentsize, 1)
    result = ident + header + struct.pack(program_format, *program)
    result += b'\x00' * (interp_offset - len(result))
    return result + interp.encode() + b'\x00'

class SparseBytes:
    """A seekable byte stream that permits ELF-sized sparse offsets."""

    def __init__(self, data):
        self.data = data
        self.position = 0

    def read(self, size=-1):
        if self.position >= len(self.data):
            return b''
        if size < 0:
            result = self.data[self.position:]
            self.position = len(self.data)
            return result
        result = self.data[self.position:self.position + size]
        self.position += len(result)
        return result

    def seek(self, position):
        if position < 0:
            raise ValueError('negative seek')
        self.position = position
        return position

@pytest.mark.parametrize('capacity, encoding', [(1, 1), (1, 2), (2, 1), (2, 2)])
def test_header_fields_are_unsigned_for_all_layouts(capacity, encoding):
    elf = ELFFile(io.BytesIO(make_elf(capacity, encoding, machine=32771, flags=2147483649)))
    assert elf.machine == 32771
    assert elf.flags == 2147483649

def test_valid_magic_and_capacity_are_read_from_the_correct_identification_bytes():
    elf = ELFFile(io.BytesIO(make_elf(2, 1, machine=62)))
    assert elf.capacity == 2
    assert elf.encoding == 1
    assert elf.machine == 62

def test_identification_is_read_as_unsigned_bytes():
    ident = b'\x7fELF' + bytes([1, 1]) + b'\x00\x00\xff' + b'\x00' * 7
    header = struct.pack('<HHIIIIIHHH', 2, 3, 1, 0, 52, 0, 0, 52, 32, 0)
    elf = ELFFile(io.BytesIO(ident + header))
    assert elf.machine == 3

def test_invalid_magic_reports_the_actual_magic_bytes():
    with pytest.raises(ELFInvalid) as error:
        ELFFile(io.BytesIO(b'\xffELF' + b'\x00' * 12))
    assert str(error.value) == "invalid magic: b'\\xffELF'"

def test_short_identification_has_a_specific_error_message():
    with pytest.raises(ELFInvalid) as error:
        ELFFile(io.BytesIO(b'\x7fELF'))
    assert str(error.value) == 'unable to parse identification'

def test_unsupported_capacity_or_encoding_has_a_specific_error_message():
    ident = b'\x7fELF' + bytes([3, 1]) + b'\x00' * 10
    with pytest.raises(ELFInvalid) as error:
        ELFFile(io.BytesIO(ident))
    assert str(error.value) == 'unrecognized capacity (3) or encoding (1)'

def test_short_elf_header_has_a_specific_error_message():
    ident = b'\x7fELF' + bytes([1, 1]) + b'\x00' * 10
    with pytest.raises(ELFInvalid) as error:
        ELFFile(io.BytesIO(ident))
    assert str(error.value) == 'unable to parse machine and section information'
