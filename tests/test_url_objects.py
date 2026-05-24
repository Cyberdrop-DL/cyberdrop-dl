import pytest

from cyberdrop_dl.url_objects import _extract_last_domain, _has_domain, _remove_domain_if_duplicate


@pytest.mark.parametrize(
    ("folder", "expected"),
    [
        ("Loose Files (JPG5)", True),
        ("Loose Files", False),
    ],
)
def test_has_domain(folder: str, *, expected: bool) -> None:
    assert _has_domain(folder) is expected


def test_extract_last_domain() -> None:
    folders = (
        "Loose Files (mega.nz)",
        "Loose Files",
        "Loose Files (bunkr)",
        "Loose Files [bunkr] (JPG5)",
        "Loose Files",
    )
    assert _extract_last_domain(folders) == "JPG5"


@pytest.mark.parametrize(
    ("folder", "domain", "expected"),
    [
        ("Loose Files [bunkr] (JPG5)", "JPG5", "Loose Files [bunkr]"),
        ("Loose Files [bunkr] (JPG5)", "bunkr", "Loose Files [bunkr] (JPG5)"),
        ("Loose Files [bunkr]", "bunkr", "Loose Files [bunkr]"),
    ],
)
def test_remove_domain_if_duplicate(folder: str, domain: str, expected: str) -> None:
    assert _remove_domain_if_duplicate(folder, domain) == expected
