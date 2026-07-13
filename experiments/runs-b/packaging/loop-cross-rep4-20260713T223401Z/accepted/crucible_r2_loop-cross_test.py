import io
import struct
import pytest
from packaging._elffile import ELFFile

class SparseBytes:
    """A seekable byte source that permits ELF-sized sparse offsets."""

    def __init__(self, data):
        self.data = data
        self.position = 0

    def read(self, size=-1):
        if self.position >= len(self.data):
            return b''
        if size is None or size < 0:
            result = self.data[self.position:]
            self.position = len(self.data)
            return result
        result = self.data[self.position:self.position + size]
        self.position += len(result)
        return result

    def seek(self, offset, whence=0):
        if whence != 0:
            raise ValueError('only absolute seeks are used by ELFFile')
        if offset < 0:
            raise ValueError('negative seek position')
        self.position = offset
        return offset

def make_elf(capacity, encoding, *, machine=62, abi_version=0, program_offset=200, program_vaddr=220, program_filesz=5, program_memsz=2):
    byte_order = '<' if encoding == 1 else '>'
    ident = b'\x7fELF' + bytes([capacity, encoding, abi_version]) + b'\x00' * 9
    if capacity == 1:
        header_format = byte_order + 'HHIIIIIHHH'
        program_format = byte_order + 'IIIIIIII'
        header_size = 52
        program_size = 32
        header = struct.pack(header_format, 2, machine, 1, 0, header_size, 0, 305419896, header_size, program_size, 1)
        program = struct.pack(program_format, 3, program_offset, program_vaddr, 0, program_filesz, program_memsz, 7, 1)
    else:
        header_format = byte_order + 'HHIQQQIHHH'
        program_format = byte_order + 'IIQQQQQQ'
        header_size = 64
        program_size = 56
        header = struct.pack(header_format, 2, machine, 1, 0, header_size, 0, 305419896, header_size, program_size, 1)
        program = struct.pack(program_format, 3, 7, program_offset, program_vaddr, 0, program_filesz, program_memsz, 1)
    data = bytearray(ident + header + program)
    if program_offset < 1000000:
        if len(data) < program_offset + program_filesz:
            data.extend(b'\x00' * (program_offset + program_filesz - len(data)))
        data[program_offset:program_offset + 5] = b'good\x00'
    return bytes(data)

@pytest.mark.parametrize(('capacity', 'encoding'), [(1, 1), (1, 2), (2, 1), (2, 2)])
def test_machine_is_an_unsigned_elf_header_field(capacity, encoding):
    elf = ELFFile(io.BytesIO(make_elf(capacity, encoding, machine=32768)))
    assert elf.machine == 32768
