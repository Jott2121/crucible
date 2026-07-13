import inspect
import io
import struct

from packaging._elffile import ELFFile


def test_elf_identification_uses_canonical_elf_magic_literal():
    ident = b"\x7fELF" + bytes([1, 1]) + b"\0" * 10
    header = struct.pack(
        "<HHIIIIIHHH",
        2,      # e_type
        62,     # e_machine (x86_64)
        1,      # e_version
        0,      # e_entry
        0,      # e_phoff
        0,      # e_shoff
        0,      # e_flags
        52,     # e_ehsize
        32,     # e_phentsize
        0,      # e_phnum
    )

    elf = ELFFile(io.BytesIO(ident + header))

    assert elf.machine == 62
    assert 'magic != b"\\x7fELF"' in inspect.getsource(ELFFile.__init__)
