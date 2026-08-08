import pytest

from cyberdrop_dl.crawlers.hohoj_tv import _dvd_code


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("[Chinese Sub]STARS-094 [Uncensored Leaked Version] Iori Furukawa", "STARS-094"),
        ("[Uncensored]fc2-ppv 3883539 Having sex with Kaoki's mistress until morning", "FC2-PPV 3883539"),
        ("[Uncensored]062224_01 Let the toy cat on the cat Mayuka Yabe", "062224_01"),
        ("062224_01 Let the toy cat on the cat Mayuka Yabe", "062224_01"),
        ("OAE-165 Yua Mikami cried. Yua Mikami", "OAE-165"),
        (
            "DoctorAdventures.20.08.29 The Last Dick On Earth: Remastered Johnny Sins Nicole Aniston Romi Rain Anna Bell Peaks",
            "DoctorAdventures.20.08.29 The Last Dick On Earth",
        ),
    ],
)
def test_dvd_code(title: str, expected: str) -> None:
    assert _dvd_code(title) == expected
