import pytest

from cyberdrop_dl.crawlers import archive_org


@pytest.mark.parametrize(
    ("base_path", "path", "result"),
    [
        (None, "Anime_Campuran", True),
        (
            "Anime_Campuran/Anime_Campuran.thumbs",
            "Anime_Campuran/Anime_Campuran.thumbs/%5BErai-raws%5D%20Karakai%20Jouzu%20no%20Takagi-san%202%20-%2011%20%5B1080p%5D_000001.jpg",
            True,
        ),
        (
            "Anime_Campuran/Anime_Campuran.thumbs",
            "Anime_Campuran/images/%5BErai-raws%5D%20Karakai%20Jouzu%20no%20Takagi-san%202%20-%2011%20%5B1080p%5D_000001.jpg",
            False,
        ),
        (
            "2-05+When+a+Camera+Fails.mp4",
            "2-05 When a Camera Fails.mp4",
            True,
        ),
        (
            "2-05+When+a+Camera+Fails.mp4",
            "2-05+When+a+Camera+Fails.mp4",
            True,
        ),
        (
            "2-05+When+a+Camera+Fails.mp4",
            "/2-05 When a Camera Fails.mp4",
            False,
        ),
    ],
)
def test_is_subpath(base_path: str | None, path: str, *, result: bool) -> None:
    assert archive_org._is_subpath(base_path, path) is result
