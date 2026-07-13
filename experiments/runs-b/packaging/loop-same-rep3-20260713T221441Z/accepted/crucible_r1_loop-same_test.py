import io
import struct
import pytest
from packaging._elffile import ELFFile, ELFInvalid
E_FMTS = {(1, 1): '<HHIIIIIHHH', (1, 2): '>HHIIIIIHHH', (2, 1): '<HHIQQQIHHH', (2, 2): '>HHIQQQIHHH'}
P_FMTS = {(1, 1): '<IIIIIIII', (1, 2): '>IIIIIIII', (2, 1): '<IIQQQQQQ', (2, 2): '>IIQQQQQQ'}

def build_header(capacity, encoding, machine, flags, phoff, phentsize, phnum):
    ident = bytes([127, 69, 76, 70, capacity, encoding] + [0] * 10)
    e_fmt = E_FMTS[capacity, encoding]
    header = struct.pack(e_fmt, 2, machine, 1, 0, phoff, 0, flags, struct.calcsize(e_fmt) + 16, phentsize, phnum)
    return ident + header

def build_full_elf(capacity, encoding, interp_string):
    e_fmt = E_FMTS[capacity, encoding]
    p_fmt = P_FMTS[capacity, encoding]
    header_size = struct.calcsize(e_fmt) + 16
    phentsize = struct.calcsize(p_fmt)
    phoff = header_size
    phnum = 1
    interp_bytes = interp_string.encode('ascii') + b'\x00'
    padding = b'NOTPART0123'
    interp_offset = phoff + phentsize
    ident = bytes([127, 69, 76, 70, capacity, encoding] + [0] * 10)
    header = struct.pack(e_fmt, 2, 62, 1, 0, phoff, 0, 0, header_size, phentsize, phnum)
    if capacity == 1:
        fields = (3, interp_offset, 11, 22, len(interp_bytes), 33, 44, 55)
    else:
        fields = (3, 44, interp_offset, 11, 22, len(interp_bytes), 33, 55)
    ph = struct.pack(p_fmt, *fields)
    return ident + header + ph + interp_bytes + padding

def test_invalid_magic_message():
    bad = b'\x00ELF' + bytes(12)
    f = io.BytesIO(bad)
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(f)
    message = str(excinfo.value)
    assert 'invalid magic' in message
    assert repr(b'\x00ELF') in message

def test_unable_to_parse_identification_message():
    f = io.BytesIO(b'\x7fEL')
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(f)
    assert 'unable to parse identification' in str(excinfo.value)

def test_unable_to_parse_machine_message():
    ident = bytes([127, 69, 76, 70, 1, 1] + [0] * 10)
    f = io.BytesIO(ident)
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(f)
    assert 'unable to parse machine and section information' in str(excinfo.value)

def test_unrecognized_capacity_message():
    ident = bytes([127, 69, 76, 70, 9, 9] + [0] * 10)
    f = io.BytesIO(ident)
    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(f)
    message = str(excinfo.value)
    assert 'unrecognized capacity' in message
    assert '9' in message

@pytest.mark.parametrize('capacity,encoding', [(1, 1), (1, 2), (2, 1), (2, 2)])
def test_header_fields_parsed_correctly(capacity, encoding):
    flags_sentinel = 3735928559
    if capacity == 1:
        phoff_sentinel = 4294967294
    else:
        phoff_sentinel = 18446744073709551614
    machine_sentinel = 62
    data = build_header(capacity, encoding, machine=machine_sentinel, flags=flags_sentinel, phoff=phoff_sentinel, phentsize=0, phnum=0)
    f = io.BytesIO(data)
    ef = ELFFile(f)
    assert ef.capacity == capacity
    assert ef.encoding == encoding
    assert ef.machine == machine_sentinel
    assert ef.flags == flags_sentinel
    assert ef._e_phoff == phoff_sentinel
    assert ef.interpreter is None

@pytest.mark.parametrize('capacity,encoding', [(1, 2), (2, 1)])
def test_interpreter_field_positions(capacity, encoding):
    interp_string = '/lib/ld-sentinel.so'
    data = build_full_elf(capacity, encoding, interp_string)
    f = io.BytesIO(data)
    ef = ELFFile(f)
    assert ef.interpreter == interp_string
