import sys
from pathlib import Path

import pytest

from cyberdrop_dl.filepath import remove_emojis_and_symbols, sanitize_filename

IS_MACOS = sys.platform == "darwin"


FOREIGN_LENGUAGE_STRINGS = ["これは単なるテストです", "это всего лишь тест", "این فقط یک آزمایش است", "هذا مجرد اختبار"]
INVALID_UNICODE9_STRING = "🫧Bubblz🫧"

pytestmark = pytest.mark.filterwarnings("ignore:invalid escape sequence.*::SyntaxWarning")


def test_sanitize_macos_problematic_unicode_symbol() -> None:
    assert remove_emojis_and_symbols(INVALID_UNICODE9_STRING) == "Bubblz"


@pytest.mark.parametrize("name", FOREIGN_LENGUAGE_STRINGS)
def test_sanitization_must_keep_other_languages_chars(name: str) -> None:
    assert remove_emojis_and_symbols(name) == name


@pytest.mark.skipif(not IS_MACOS, reason="Only fails in older macOS with APFS")
@pytest.mark.xfail
def test_unicode9_filename_raise_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        tmp_path.joinpath(INVALID_UNICODE9_STRING).with_suffix(".txt").write_text("OK")


@pytest.mark.parametrize("name", [INVALID_UNICODE9_STRING, *FOREIGN_LENGUAGE_STRINGS])
def test_sanitized_filename_do_not_raise_os_errors(name: str, tmp_path: Path) -> None:
    filename = sanitize_filename(name)
    tmp_path.joinpath(filename).with_suffix(".txt").write_text("OK")
