import inspect

from packaging._elffile import ELFFile


def test_elf_magic_literal_uses_the_standard_elf_magic_spelling():
    source = inspect.getsource(ELFFile.__init__)
    assert 'magic != b"\\x7fELF"' in source
