import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid, EIClass, EIData, EMachine


def build_elf_header(
    machine=int(EMachine.X8664),
    capacity=int(EIClass.C64),
    encoding=int(EIData.Lsb),
    e_phoff=64,
    e_phentsize=56,
    e_phnum=1,
    flags=0,
    magic=b"\x7fELF",
):
    """Construct a minimal valid 64-bit little-endian ELF header."""
    ident = magic + bytes([capacity, encoding]) + bytes(10)
    e_fmt = "<HHIQQQIHHH"
    header = struct.pack(
        e_fmt,
        2,  # e_type
        machine,
        1,  # e_version
        0,  # e_entry
        e_phoff,
        0,  # e_shoff
        flags,
        64,  # e_ehsize
        e_phentsize,
        e_phnum,
    )
    return ident + header


def test_valid_elf_header_parses_correctly():
    data = build_elf_header()
    f = io.BytesIO(data)
    elf = ELFFile(f)

    assert elf.capacity == EIClass.C64
    assert elf.encoding == EIData.Lsb
    assert elf.machine == EMachine.X8664
    assert elf.flags == 0
    assert elf._e_phoff == 64
    assert elf._e_phentsize == 56
    assert elf._e_phnum == 1


def test_invalid_magic_byte_raises_elfinvalid():
    # Corrupt the very first magic byte (0x7f) so it no longer matches.
    data = bytearray(build_elf_header())
    data[0] = 0x00
    f = io.BytesIO(bytes(data))
    with pytest.raises(ELFInvalid):
        ELFFile(f)


def test_correct_magic_prefix_is_required_exactly():
    # Verify that the exact byte 0x7f (DEL) followed by "ELF" is accepted,
    # and that any different first byte is rejected, independent of case
    # of any hex-escape representation used internally.
    good_data = build_elf_header(magic=b"\x7fELF")
    f_good = io.BytesIO(good_data)
    # Should not raise.
    elf = ELFFile(f_good)
    assert elf.machine == EMachine.X8664

    bad_data = build_elf_header(magic=b"\x7eELF")  # one less than 0x7f
    f_bad = io.BytesIO(bad_data)
    with pytest.raises(ELFInvalid):
        ELFFile(f_bad)


def test_interpreter_reads_pt_interp_section():
    # Build an ELF with one program header entry of type PT_INTERP (3).
    interp_path = b"/lib64/ld-linux-x86-64.so.2\x00"
    e_phoff = 120
    e_phentsize = 56  # size of 64-bit program header per p_fmt "<IIQQQQQQ"
    e_phnum = 1

    header = build_elf_header(
        e_phoff=e_phoff, e_phentsize=e_phentsize, e_phnum=e_phnum
    )

    # Program header: p_fmt = "<IIQQQQQQ" -> p_type, p_flags, p_offset,
    # p_vaddr, p_paddr, p_filesz, p_memsz, p_align
    interp_offset = e_phoff + e_phentsize + 8  # place string after headers
    p_type = 3  # PT_INTERP
    p_offset = interp_offset
    p_filesz = len(interp_path)
    program_header = struct.pack(
        "<IIQQQQQQ",
        p_type,
        0,  # p_flags
        p_offset,
        0,  # p_vaddr
        0,  # p_paddr
        p_filesz,
        0,  # p_memsz
        0,  # p_align
    )

    # Build full file: header + program header + padding + interp string.
    content = bytearray(header)
    content += bytes(e_phoff - len(content))  # pad up to e_phoff
    content += program_header
    content += bytes(interp_offset - len(content))  # pad up to string offset
    content += interp_path

    f = io.BytesIO(bytes(content))
    elf = ELFFile(f)
    assert elf.interpreter == "/lib64/ld-linux-x86-64.so.2"
