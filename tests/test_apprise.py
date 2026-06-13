import logging
import os
from pathlib import Path

import pytest

from cyberdrop_dl.utils.apprise import read_apprise_urls


class TestReadAppriseUrls:
    def test_valid_file(self, tmp_path: Path) -> None:
        apprise_file = tmp_path / "urls.txt"
        _ = apprise_file.write_text(
            "\n".join(
                (
                    "mailto://user:pass@example.com",
                    " ",
                    "# comment",
                    "tgram://bottoken/chatid\n",
                )
            )
        )
        assert read_apprise_urls(apprise_file) == (
            "mailto://user:pass@example.com",
            "tgram://bottoken/chatid",
        )

    def test_empty_file(self, tmp_path: Path) -> None:
        apprise_file = tmp_path / "empty.txt"
        apprise_file.touch()
        assert read_apprise_urls(apprise_file) == ()

    def test_only_comments_and_whitespace(self, tmp_path: Path) -> None:
        apprise_file = tmp_path / "comments.txt"
        _ = apprise_file.write_text("\n".join(("# line1\n", "  # line2\n\t\n")))
        assert read_apprise_urls(apprise_file) == ()

    def test_missing_file_does_not_raise_error(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        apprise_file = tmp_path / "gone.txt"
        with caplog.at_level(logging.ERROR):
            assert read_apprise_urls(apprise_file) == ()

        assert "Unable to read apprise URL" not in caplog.text

    @pytest.mark.skipif(os.name == "nt", reason="chmod not on Windows")
    def test_permission_error(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        apprise_file = tmp_path / "no_access.txt"
        _ = apprise_file.write_text("mailto://a@b.c")

        _ = apprise_file.chmod(0o000)
        try:
            with caplog.at_level(logging.ERROR):
                assert read_apprise_urls(apprise_file) == ()

            assert "Unable to read apprise URL" in caplog.text
        finally:
            _ = apprise_file.chmod(0o644)  # restore for cleanup
