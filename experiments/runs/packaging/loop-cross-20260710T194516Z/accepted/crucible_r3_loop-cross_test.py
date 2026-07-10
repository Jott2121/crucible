import inspect

from packaging._elffile import ELFFile


def test_elf_magic_check_uses_canonical_lowercase_hex_escape():
    source = inspect.getsource(ELFFile.__init__)
    assert 'b"\\x7fELF"' in source
