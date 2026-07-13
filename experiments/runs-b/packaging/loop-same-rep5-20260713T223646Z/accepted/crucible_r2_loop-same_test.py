import io
import struct

import pytest

from packaging._elffile import ELFFile


def _build_elf(capacity, encoding, interp_bytes, extra_bytes):
    """
    Build a minimal, valid ELF byte blob with a single PT_INTERP program
    header entry, for a given (capacity, encoding) combination.

    `interp_bytes` is the exact content that should be read as p_filesz
    bytes (the "correct" interpreter payload, including its NUL
    terminator). `extra_bytes` is additional, non-null padding placed
    right after it in the file so that p_memsz > p_filesz. If the code
    incorrectly uses p_memsz (or another wrong field) instead of
    p_filesz to determine how many bytes to read, the extra bytes will
    leak into the result.
    """
    ident = bytes([0x7F, 0x45, 0x4C, 0x46, capacity, encoding] + [0] * 10)

    if capacity == 1:
        e_fmt = "<HHIIIIIHHH" if encoding == 1 else ">HHIIIIIHHH"
        p_fmt = "<IIIIIIII" if encoding == 1 else ">IIIIIIII"
    else:
        e_fmt = "<HHIQQQIHHH" if encoding == 1 else ">HHIQQQIHHH"
        p_fmt = "<IIQQQQQQ" if encoding == 1 else ">IIQQQQQQ"

    e_phentsize = struct.calcsize(p_fmt)
    e_phoff = 16 + struct.calcsize(e_fmt)
    e_phnum = 1

    # e_type, e_machine, e_version, e_entry, e_phoff, e_shoff,
    # e_flags, e_ehsize, e_phentsize, e_phnum
    header = struct.pack(
        e_fmt, 0, 0, 0, 0, e_phoff, 0, 0, 0, e_phentsize, e_phnum
    )

    interp_offset = e_phoff + e_phentsize
    filesz = len(interp_bytes)
    memsz = filesz + len(extra_bytes)

    if capacity == 1:
        # Elf32_Phdr: p_type, p_offset, p_vaddr, p_paddr, p_filesz,
        # p_memsz, p_flags, p_align
        phdr = struct.pack(p_fmt, 3, interp_offset, 0, 0, filesz, memsz, 0, 0)
    else:
        # Elf64_Phdr: p_type, p_flags, p_offset, p_vaddr, p_paddr,
        # p_filesz, p_memsz, p_align
        phdr = struct.pack(p_fmt, 3, 0, interp_offset, 0, 0, filesz, memsz, 0)

    return ident + header + phdr + interp_bytes + extra_bytes


@pytest.mark.parametrize(
    "capacity, encoding",
    [
        (1, 1),  # 32-bit LSB
        (1, 2),  # 32-bit MSB
        (2, 1),  # 64-bit LSB
        (2, 2),  # 64-bit MSB
    ],
)
def test_interpreter_uses_filesz_not_memsz(capacity, encoding):
    interp_bytes = b"/opt/interp\0"
    extra_bytes = b"XYZ"  # non-null padding beyond p_filesz

    data = _build_elf(capacity, encoding, interp_bytes, extra_bytes)
    elf = ELFFile(io.BytesIO(data))

    # The correct behavior reads exactly p_filesz bytes and strips
    # NUL characters from the ends, yielding a clean path with no
    # trailing garbage from beyond p_filesz.
    expected = interp_bytes.decode("ascii").strip("\0")
    assert expected == "/opt/interp"

    assert elf.interpreter == expected


def test_interpreter_content_is_exact_for_64bit_lsb():
    # A focused sanity check independent of the parametrized helper,
    # explicitly verifying the resulting string length matches filesz,
    # not memsz.
    interp_bytes = b"/lib64/ld-linux-x86-64.so.2\0"
    extra_bytes = b"garbage-that-should-not-appear"

    data = _build_elf(2, 1, interp_bytes, extra_bytes)
    elf = ELFFile(io.BytesIO(data))

    result = elf.interpreter
    assert result == "/lib64/ld-linux-x86-64.so.2"
    assert "garbage" not in result
