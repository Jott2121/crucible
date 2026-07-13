import inspect

from packaging._elffile import ELFFile


def test_elf_magic_check_uses_canonical_lowercase_hex_literal():
    source = inspect.getsource(ELFFile.__init__)
    assert 'if magic != b"\\x7fELF":' in source
