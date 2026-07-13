import io
import struct

import pytest

from packaging._elffile import ELFFile, ELFInvalid


def _build_elf(capacity: int, encoding: int, machine: int, interp: bytes) -> bytes:
    """
    Build a minimal but structurally valid ELF file (ident + header +
    one PT_INTERP program header + interpreter string) for the given
    capacity (1=32bit, 2=64bit) and encoding (1=LSB, 2=MSB).
    """
    endian = "<" if encoding == 1 else ">"

    if capacity == 1:
        e_fmt = endian + "HHIIIIIHHH"
        p_fmt = endian + "IIIIIIII"
    else:
        e_fmt = endian + "HHIQQQIHHH"
        p_fmt = endian + "IIQQQQQQ"

    ident = bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding]) + bytes(10)

    header_size = struct.calcsize(e_fmt)
    ph_size = struct.calcsize(p_fmt)

    e_phoff = len(ident) + header_size
    interp_off = e_phoff + ph_size
    interp_data = interp + b"\x00"

    if capacity == 1:
        header = struct.pack(
            e_fmt,
            0,  # e_type
            machine,  # e_machine
            0,  # e_version
            0,  # e_entry
            e_phoff,  # e_phoff
            0,  # e_shoff
            0,  # e_flags
            0,  # e_ehsize
            ph_size,  # e_phentsize
            1,  # e_phnum
        )
        ph = struct.pack(
            p_fmt,
            3,  # p_type = PT_INTERP
            interp_off,  # p_offset
            0,  # p_vaddr
            0,  # p_paddr
            len(interp_data),  # p_filesz
            0,  # p_memsz
            0,  # p_flags
            0,  # p_align
        )
    else:
        header = struct.pack(
            e_fmt,
            0,  # e_type
            machine,  # e_machine
            0,  # e_version
            0,  # e_entry
            e_phoff,  # e_phoff
            0,  # e_shoff
            0,  # e_flags
            0,  # e_ehsize
            ph_size,  # e_phentsize
            1,  # e_phnum
        )
        ph = struct.pack(
            p_fmt,
            3,  # p_type = PT_INTERP
            0,  # p_flags
            interp_off,  # p_offset
            0,  # p_vaddr
            0,  # p_paddr
            len(interp_data),  # p_filesz
            0,  # p_memsz
            0,  # p_align
        )

    return ident + header + ph + interp_data


@pytest.mark.parametrize(
    "capacity,encoding",
    [(1, 1), (1, 2), (2, 1), (2, 2)],
)
def test_elffile_parses_all_capacity_encoding_combinations(capacity, encoding):
    machine = 62  # X8664
    interp = b"/lib64/ld-linux.so.2"
    data = _build_elf(capacity, encoding, machine, interp)

    elf = ELFFile(io.BytesIO(data))

    assert elf.capacity == capacity
    assert elf.encoding == encoding
    assert elf.machine == machine
    assert elf.interpreter == interp.decode("ascii")


def test_capacity_is_read_from_correct_byte_index():
    # capacity byte (index 4) differs from encoding byte (index 5); if the
    # implementation mistakenly reads capacity from index 5 the resulting
    # capacity would be wrong.
    capacity = 1
    encoding = 2
    machine = 62
    interp = b"/lib/ld.so"
    data = _build_elf(capacity, encoding, machine, interp)

    elf = ELFFile(io.BytesIO(data))

    assert elf.capacity == 1
    assert elf.encoding == 2


def test_invalid_magic_raises_with_expected_message():
    magic = b"XELF"
    data = magic + bytes(12)  # 16 bytes total, wrong magic
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(data))

    expected_message = f"invalid magic: {magic!r}"
    assert str(exc_info.value) == expected_message


def test_too_short_for_identification_raises_expected_message():
    data = b"\x7f\x45\x4c"  # only 3 bytes, can't even read the 16-byte ident
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(data))

    assert str(exc_info.value) == "unable to parse identification"


def test_unrecognized_capacity_encoding_raises_expected_message():
    # Valid magic, but capacity/encoding combination (9, 9) is not supported.
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, 9, 9]) + bytes(10)
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(ident))

    assert str(exc_info.value) == "unrecognized capacity (9) or encoding (9)"


def test_truncated_after_ident_raises_expected_message():
    # Valid magic + valid capacity/encoding (32-bit LSB), but no further
    # bytes for the ELF header itself.
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, 1, 1]) + bytes(10)
    with pytest.raises(ELFInvalid) as exc_info:
        ELFFile(io.BytesIO(ident))

    assert str(exc_info.value) == "unable to parse machine and section information"


def test_interpreter_and_machine_for_32bit_lsb():
    machine = 3  # I386
    interp = b"/lib/ld-linux.so.2"
    data = _build_elf(1, 1, machine, interp)

    elf = ELFFile(io.BytesIO(data))

    assert elf.machine == 3
    assert elf.interpreter == interp.decode("ascii")


def test_interpreter_and_machine_for_64bit_msb():
    machine = 183  # AArch64
    interp = b"/lib/ld-linux-aarch64.so.1"
    data = _build_elf(2, 2, machine, interp)

    elf = ELFFile(io.BytesIO(data))

    assert elf.machine == 183
    assert elf.interpreter == interp.decode("ascii")
