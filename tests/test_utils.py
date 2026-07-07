from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

import pytest

from cyberdrop_dl.exceptions import InvalidExtensionError, NoExtensionError
from cyberdrop_dl.filepath import get_filename_and_ext
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils._url import fix_multi_slashes, parse_http_url


class TestGetFilenameAndExt:
    _file = Path("Cyberdrop-DL.v8.4.0.zip")

    def _ext(self, *args: Any, **kwargs: Any) -> str:
        return get_filename_and_ext(*args, **kwargs)[1]

    def _name(self, *args: Any, **kwargs: Any) -> str:
        return get_filename_and_ext(*args, **kwargs)[0]

    def test_ext_should_always_be_lowercase(self) -> None:
        exts = [self._ext(self._file.with_suffix(ext).name) for ext in (".zip", ".Zip", ".zIP", ".ziP")]
        assert exts == [".zip"] * len(exts)

    def test_ext_should_not_include_multiple_suffixes(self) -> None:
        file = self._file.name + ".rar"
        assert self._ext(file) == ".rar"

    @pytest.mark.parametrize(
        ("name", "mimetype", "expected_ext"),
        [
            ("archive", "application/zip", ".zip"),
            ("Katalina Kyle, Savanah Storm - What If She Hears Us!", "video/mp4", ".mp4"),
        ],
    )
    def test_mime_type_fallback(self, name: str, mimetype: str, expected_ext: str) -> None:
        filename, ext = get_filename_and_ext(name, mime_type=mimetype)
        assert ext == expected_ext
        assert filename == name + expected_ext

    @pytest.mark.skipif(platform.system() in {"Windows", "Darwin"}, reason="Emojis are stripped on Windows and MacOS")
    @pytest.mark.parametrize(
        ("name", "expected_name", "expected_ext"),
        [
            ("Vídeo de verificación [uvfdtpm4c2a]/video.MP4", "Vídeo de verificación [uvfdtpm4c2a]-video.mp4", ".mp4"),
            (
                "Katalina Kyle, Savanah Storm - “What If She Hears Us! 🍕”.mp4",
                "Katalina Kyle, Savanah Storm - “What If She Hears Us! 🍕”.mp4",
                ".mp4",
            ),
        ],
    )
    def test_complex_name(self, name: str, expected_name: str, expected_ext: str) -> None:
        name, ext = get_filename_and_ext(name)
        assert ext == expected_ext
        assert name == expected_name

    @pytest.mark.parametrize(
        "mime_type",
        [
            "application/zip",
            "application/pdf",
            "image/png",
            "video/mp4",
            "text/plain",
            "application/json",
            "image/jpeg",
        ],
    )
    def test_mime_type_should_be_ignore_if_the_file_has_a_valid_ext(self, mime_type: str) -> None:
        filename, ext = get_filename_and_ext(self._file.name, mime_type=mime_type)
        assert ext == self._file.suffix
        assert filename == self._file.name

    @pytest.mark.parametrize(
        ("name", "expected_name", "expected_ext"),
        [
            ("img_3763-webp.6091490", "img_3763.webp", ".webp"),
            ("1-gif.5021643", "1.gif", ".gif"),
        ],
    )
    def test_forum_filename(self, name: str, expected_name: str, expected_ext: str) -> None:
        name, ext = get_filename_and_ext(name, xenforo=True)
        assert ext == expected_ext
        assert name == expected_name

    def test_long_extension_should_raise_invalid_ext_error(self) -> None:
        with pytest.raises(InvalidExtensionError):
            get_filename_and_ext("video.abcdef")

    def test_no_extension_should_raise_no_ext_error(self) -> None:
        with pytest.raises(NoExtensionError):
            get_filename_and_ext("README")


@pytest.mark.parametrize(
    "url",
    [
        "http:/s",
        "https://google",
        "/path/to/file",
        "file",
        "/example.com/file",
    ],
)
def test_parsing_invalid_url(url: str) -> None:
    with pytest.raises(ValueError, match="URL"):
        parse_http_url(url)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http:////google.com", "http://google.com"),
        ("https://////google.com", "https://google.com"),
        ("http:/google.com", "http:/google.com"),
        ("//google.com", "//google.com"),
        ("/google.com", "/google.com"),
        ("https://example.com////bar", "https://example.com////bar"),
    ],
)
def test_fix_multi_slashes(url: str, expected: str) -> None:
    assert fix_multi_slashes(url) == expected


@pytest.mark.parametrize(
    ("url", "origin", "trim", "expected"),
    [
        ("http://localhost", None, False, "http://localhost/"),
        ("https://////example.com/file//a//b/", None, False, "https://example.com/file//a//b/"),
        ("https://////example.com/file//a//b/", None, True, "https://example.com/file//a//b"),
        ("https://////example.com/file/", None, True, "https://example.com/file"),
        ("https://example.com/file/video.mp4?a=1+b=2", None, True, "https://example.com/file/video.mp4?a=1 b%3D2"),
        (
            "https://example.com/video/file/%E6%92%AE%E5%BD%B1%E4%BC%9A",
            None,
            False,
            "https://example.com/video/file/撮影会",
        ),
        ("//example.com/file", "https://example.net", False, "https://example.com/file"),
        ("example.com/file", "https://example.net", False, "https://example.net/example.com/file"),
        ("/example.com/file", "https://example.net", False, "https://example.net/example.com/file"),
    ],
)
def test_parse_http(url: str, origin: str | None, expected: str, *, trim: bool) -> None:
    result = parse_http_url(url, AbsoluteHttpURL(origin) if origin else None, trim=trim)
    assert result.human_repr() == expected
