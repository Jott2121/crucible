import io

import pytest

from packaging._elffile import ELFFile, ELFInvalid


def test_capacity_byte_is_read_as_unsigned():
    """
    The ELF header's capacity byte must be interpreted as an *unsigned*
    8-bit value (format code "B"), not as a signed one ("b"). If it were
    read as signed, a byte value of 200 would show up as -56 instead of
    200, which changes the error message produced when the capacity is
    not recognized.
    """
    # Construct a fake ELF header:
    #   bytes 0-3: magic "\x7fELF"
    #   byte 4: capacity = 200 (invalid, not 1 or 2)
    #   byte 5: encoding = 1 (valid LSB encoding)
    #   bytes 6-15: padding, unused
    data = b"\x7fELF" + bytes([200, 1]) + bytes(10)

    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(data))

    message = str(excinfo.value)

    # On correct (unsigned) parsing, the capacity value reported should be 200.
    assert "200" in message
    # If parsed as signed, 200 would become 200 - 256 = -56.
    assert "-56" not in message


def test_encoding_byte_is_read_as_unsigned():
    """
    Similarly, the encoding byte must also be interpreted as unsigned.
    """
    # bytes 0-3: magic "\x7fELF"
    # byte 4: capacity = 1 (valid 32-bit)
    # byte 5: encoding = 200 (invalid, not 1 or 2)
    data = b"\x7fELF" + bytes([1, 200]) + bytes(10)

    with pytest.raises(ELFInvalid) as excinfo:
        ELFFile(io.BytesIO(data))

    message = str(excinfo.value)

    assert "200" in message
    assert "-56" not in message
