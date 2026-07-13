import idna.cli as cli


def test_convert_one_encodes_output_using_lowercase_ascii_codec(monkeypatch, capsys):
    class EncodedDomain:
        def decode(self, encoding):
            assert encoding == "ascii"
            return "xn--bcher-kva.example"

    def fake_encode(domain, *, uts46):
        assert domain == "bücher.example"
        assert uts46 is True
        return EncodedDomain()

    monkeypatch.setattr(cli, "encode", fake_encode)

    assert cli._convert_one("bücher.example", "encode", True) is True
    assert capsys.readouterr().out == "xn--bcher-kva.example\n"


def test_looks_like_alabel_decodes_prefix_using_lowercase_ascii_codec(monkeypatch):
    class Prefix:
        def decode(self, encoding):
            assert encoding == "ascii"
            return "xn--"

    monkeypatch.setattr(cli, "_alabel_prefix", Prefix())

    assert cli._looks_like_alabel("www.XN--BCHER-KVA.example") is True
