from __future__ import annotations

import platform
from pathlib import Path

import pytest

from cyberdrop_dl.exceptions import InvalidExtensionError, NoExtensionError
from cyberdrop_dl.utils.utilities import get_filename_and_ext


class TestGetFilenameAndExt:
    _file = Path("Cyberdrop-DL.v8.4.0.zip")

    def _ext(self, *args, **kargs) -> str:
        return get_filename_and_ext(*args, **kargs)[1]

    def _name(self, *args, **kargs) -> str:
        return get_filename_and_ext(*args, **kargs)[0]

    def test_ext_should_always_be_lowercase(self) -> None:
        exts = [self._ext(self._file.with_suffix(ext).name) for ext in (".zip", ".Zip", ".zIP", ".ziP")]
        assert exts == [".zip"] * len(exts)

    def test_ext_should_not_include_multiple_suffixes(self) -> None:
        file = self._file.name + ".rar"
        assert self._ext(file) == ".rar"

    @pytest.mark.parametrize(
        "name, mimetype, expected_ext",
        [
            ("archive", "application/zip", ".zip"),
            ("Katalina Kyle, Savanah Storm - What If She Hears Us!", "video/mp4", ".mp4"),
        ],
    )
    def test_mime_type_fallback(self, name: str, mimetype: str, expected_ext: str) -> None:
        filename, ext = get_filename_and_ext(name, mime_type=mimetype)
        assert ext == expected_ext
        assert filename == name + expected_ext

    @pytest.mark.skipif(platform.system() in ("Windows", "Darwin"), reason="Emojis are stripped on Windows and MacOS")
    @pytest.mark.parametrize(
        "name, expected_name, expected_ext",
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
        "name, expected_name, expected_ext",
        [
            ("img_3763-webp.6091490", "img_3763.webp", ".webp"),
            ("1-gif.5021643", "1.gif", ".gif"),
        ],
    )
    def test_forum_filename(self, name: str, expected_name: str, expected_ext: str) -> None:
        name, ext = get_filename_and_ext(name, forum=True)
        assert ext == expected_ext
        assert name == expected_name

    def test_long_extension_should_raise_invalid_ext_error(self) -> None:
        with pytest.raises(InvalidExtensionError):
            get_filename_and_ext("video.abcdef")

    def test_no_extension_should_raise_no_ext_error(self) -> None:
        with pytest.raises(NoExtensionError):
            get_filename_and_ext("README")
