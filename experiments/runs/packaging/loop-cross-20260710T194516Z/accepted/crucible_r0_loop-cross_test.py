import io
import struct
import pytest
from packaging._elffile import ELFFile, ELFInvalid, EIClass, EIData, EMachine

def test_eiclass_values():
    assert EIClass.C32 == 1
    assert EIClass.C64 == 2

def test_eidata_values():
    assert EIData.Lsb == 1
    assert EIData.Msb == 2

def test_emachine_values():
    assert EMachine.I386 == 3
    assert EMachine.S390 == 22
    assert EMachine.Arm == 40
    assert EMachine.X8664 == 62
    assert EMachine.AArch64 == 183

def make_ident(capacity: int, encoding: int) -> bytes:
    return b'\x7fELF' + bytes([capacity, encoding]) + bytes(10)

def test_invalid_magic_raises():
    buf = b'\x7fBAD' + bytes(12)
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(buf))

def test_truncated_ident_raises():
    buf = b'\x7fELF'
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(buf))

def test_unrecognized_capacity_encoding_raises():
    buf = make_ident(3, 1)
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(buf))

def test_truncated_after_ident_raises():
    buf = make_ident(1, 1)
    with pytest.raises(ELFInvalid):
        ELFFile(io.BytesIO(buf))

def test_32bit_lsb_without_matching_interp_entry():
    ident = make_ident(1, 1)
    e_header = struct.pack('<HHIIIIIHHH', 2, 3, 1, 4096, 50, 0, 0, 50, 32, 1)
    ph_entry = struct.pack('<IIIIIIII', 1, 0, 0, 0, 0, 0, 0, 0)
    buf = ident + e_header + ph_entry
    elf = ELFFile(io.BytesIO(buf))
    assert elf.interpreter is None

def test_64bit_msb_no_phnum():
    ident = make_ident(2, 2)
    e_header = struct.pack('>HHIQQQIHHH', 2, 183, 1, 4194304, 58, 0, 0, 58, 56, 0)
    buf = ident + e_header
    elf = ELFFile(io.BytesIO(buf))
    assert elf.capacity == 2
    assert elf.encoding == 2
    assert elf.machine == 183
    assert elf.flags == 0
    assert elf.interpreter is None

def test_32bit_msb_no_phnum():
    ident = make_ident(1, 2)
    e_header = struct.pack('>HHIIIIIHHH', 2, 40, 1, 32768, 50, 0, 0, 50, 32, 0)
    buf = ident + e_header
    elf = ELFFile(io.BytesIO(buf))
    assert elf.capacity == 1
    assert elf.encoding == 2
    assert elf.machine == 40
    assert elf.flags == 0
    assert elf.interpreter is None

def test_64bit_lsb_no_phnum():
    ident = make_ident(2, 1)
    e_header = struct.pack('<HHIQQQIHHH', 2, 62, 1, 4194304, 58, 0, 0, 58, 56, 0)
    buf = ident + e_header
    elf = ELFFile(io.BytesIO(buf))
    assert elf.capacity == 2
    assert elf.encoding == 1
    assert elf.machine == 62
    assert elf.flags == 0
    assert elf.interpreter is None

def test_64bit_lsb_with_interpreter():
    ident = make_ident(2, 1)
    e_header = struct.pack('<HHIQQQIHHH', 2, 62, 1, 4194304, 58, 0, 7, 58, 56, 1)
    interp_path = b'/lib64/ld-linux-x86-64.so.2\x00'
    p_offset = 58 + 56
    ph_entry = struct.pack('<IIQQQQQQ', 3, 0, p_offset, 0, 0, len(interp_path), 0, 0)
    buf = ident + e_header + ph_entry + interp_path
    elf = ELFFile(io.BytesIO(buf))
    assert elf.flags == 7
    assert elf.interpreter == '/lib64/ld-linux-x86-64.so.2'
