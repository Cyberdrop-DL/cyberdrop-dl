import pytest

from cyberdrop_dl.crawlers import mega_nz
from cyberdrop_dl.url_objects import AbsoluteHttpURL


@pytest.mark.parametrize(
    ("url", "password", "expected"),
    [
        (
            "https://mega.nz/folder/vhESsgiQ#file/y9NE0RaD",
            "5UaDPP2wFkms2BPAFITtkg",
            "https://mega.nz/folder/vhESsgiQ#5UaDPP2wFkms2BPAFITtkg/file/y9NE0RaD",
        ),
        (
            "https://mega.nz/folder/vhESsgiQ#/file/y9NE0RaD",
            "5UaDPP2wFkms2BPAFITtkg",
            "https://mega.nz/folder/vhESsgiQ#5UaDPP2wFkms2BPAFITtkg/file/y9NE0RaD",
        ),
        (
            "https://mega.nz/folder/vhESsgiQ#///file/y9NE0RaD",
            "5UaDPP2wFkms2BPAFITtkg",
            "https://mega.nz/folder/vhESsgiQ#5UaDPP2wFkms2BPAFITtkg/file/y9NE0RaD",
        ),
        (
            "https://mega.nz/folder/vhESsgiQ",
            "5UaDPP2wFkms2BPAFITtkg",
            "https://mega.nz/folder/vhESsgiQ#5UaDPP2wFkms2BPAFITtkg",
        ),
        (
            "https://mega.nz/folder/vhESsgiQ#",
            "5UaDPP2wFkms2BPAFITtkg",
            "https://mega.nz/folder/vhESsgiQ#5UaDPP2wFkms2BPAFITtkg",
        ),
    ],
)
def test_add_password(url: str, password: str, expected: str) -> None:
    result = mega_nz._add_password(AbsoluteHttpURL(url), password)
    assert str(result) == expected
