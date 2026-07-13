import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


def _build_elf(capacity, encoding, machine, flags, interp_path):
    """
    Construct a minimal, but structurally valid, ELF binary (in memory)
    for the given capacity/encoding combination, containing a single
    PT_INTERP program header pointing at `interp_path`.
    """
    endian = "<" if encoding == 1 else ">"

    if capacity == 1:
        e_fmt = endian + "HHIIIIIHHH"
        p_fmt = endian + "IIIIIIII"
    elif capacity == 2:
        e_fmt = endian + "HHIQQQIHHH"
        p_fmt = endian + "IIQQQQQQ"
    else:
        raise ValueError("unsupported capacity")

    ident = bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding]) + bytes(10)
    assert len(ident) == 16

    header_size = struct.calcsize(e_fmt)
    phentsize = struct.calcsize(p_fmt)
    ephnum = 1
    e_phoff = 16 + header_size

    interp_bytes = interp_path.encode("utf-8") + b"\x00"
    interp_offset = e_phoff + phentsize * ephnum

    # e_type, machine, _, _, e_phoff, _, flags, _, phentsize, phnum
    header = struct.pack(
        e_fmt, 0, machine, 0, 0, e_phoff, 0, flags, 0, phentsize, ephnum
    )

    if capacity == 1:
        # p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align
        ph = struct.pack(
            p_fmt, 3, interp_offset, 0, 0, len(interp_bytes), 0, 0, 0
        )
    else:
        # p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align
        ph = struct.pack(
            p_fmt, 3, 0, interp_offset, 0, 0, len(interp_bytes), 0, 0
        )

    return ident + header + ph + interp_bytes


@pytest.mark.parametrize(
    ("capacity", "encoding"),
    [
        (1, 1),  # 32-bit LSB
        (1, 2),  # 32-bit MSB
        (2, 1),  # 64-bit LSB
        (2, 2),  # 64-bit MSB
    ],
)
def test_elffile_parses_all_formats_correctly(capacity, encoding):
    machine = 62
    flags = 0x1234
    interp_path = "/lib/ld-linux.so.2"

    data = _build_elf(capacity, encoding, machine, flags, interp_path)
    elf = ELFFile(io.BytesIO(data))

    assert elf.capacity == capacity
    assert elf.encoding == encoding
    assert elf.machine == machine
    assert elf.flags == flags
    assert elf.interpreter == interp_path


def test_elffile_32bit_lsb_field_layout_precise():
    # Distinct machine/flags/interp values to catch any index shuffling.
    machine = 3  # EMachine.I386
    flags = 0xABCD
    interp_path = "/lib/ld.so.1"

    data = _build_elf(1, 1, machine, flags, interp_path)
    elf = ELFFile(io.BytesIO(data))

    assert elf.machine == machine
    assert elf.flags == flags
    assert elf.interpreter == interp_path


def test_elffile_64bit_msb_field_layout_precise():
    machine = 183  # EMachine.AArch64
    flags = 0x5678
    interp_path = "/lib64/ld-linux-aarch64.so.1"

    data = _build_elf(2, 2, machine, flags, interp_path)
    elf = ELFFile(io.BytesIO(data))

    assert elf.machine == machine
    assert elf.flags == flags
    assert elf.interpreter == interp_path


def test_elffile_64bit_lsb_field_layout_precise():
    machine = 62  # EMachine.X8664
    flags = 0x9ABC
    interp_path = "/lib64/ld-linux-x86-64.so.2"

    data = _build_elf(2, 1, machine, flags, interp_path)
    elf = ELFFile(io.BytesIO(data))

    assert elf.machine == machine
    assert elf.flags == flags
    assert elf.interpreter == interp_path


def test_elffile_32bit_msb_field_layout_precise():
    machine = 40  # EMachine.Arm
    flags = 0x1111
    interp_path = "/lib/ld-linux-armhf.so.3"

    data = _build_elf(1, 2, machine, flags, interp_path)
    elf = ELFFile(io.BytesIO(data))

    assert elf.machine == machine
    assert elf.flags == flags
    assert elf.interpreter == interp_path


def test_elffile_invalid_identification_message():
    # Fewer than 16 bytes available -> struct.error while reading ident.
    data = b"\x7fELF\x01\x01\x00\x00"  # only 8 bytes
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(data))
    assert str(exc_info.value) == "unable to parse identification"


def test_elffile_invalid_machine_section_message():
    # Valid 16-byte identification (32-bit LSB), but truncated before the
    # rest of the ELF header can be read -> struct.error on the second read.
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, 1, 1]) + bytes(10)
    assert len(ident) == 16
    data = ident + b"\x00\x00\x00"  # not enough bytes for e_fmt

    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(data))
    assert str(exc_info.value) == "unable to parse machine and section information"
