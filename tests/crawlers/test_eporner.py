import pytest

from cyberdrop_dl.crawlers import eporner


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("744fced59f9d5ac7824daaaeb24aa3d8", "w9t04518acgxz105kb721dgwkig"),
    ],
)
def test_encode_hash(raw: str, expected: str) -> None:
    assert eporner._encode_hash(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("720p@60fps HD", 60.0),
        ("2160p(4K)@60fps HD", 60.0),
        ("1440p(2K)@60fps HD", 60.0),
        ("360p", 0.0),
    ],
)
def test_parse_fps(raw: str, expected: float) -> None:
    assert eporner._parse_fps(raw) == expected
