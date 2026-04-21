"""Tests for Fileditch Cloudflare Turnstile challenge detection."""

import pytest
from bs4 import BeautifulSoup

from cyberdrop_dl.crawlers.fileditch import _check_turnstile
from cyberdrop_dl.exceptions import DDOSGuardError

# HTML that represents a Cloudflare Turnstile challenge page (as seen at fileditchfiles.me)
TURNSTILE_CHALLENGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>File Viewer</title></head>
<body>
    <div class="modal">
        <h2>Quick security check</h2>
        <p>Complete the challenge below to access this file.</p>
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
        <div class="cf-turnstile" data-sitekey="0x4AAAAAACr63gPSW1yJcW8o"></div>
    </div>
</body>
</html>
"""

# HTML with turnstile-wrapper element
TURNSTILE_WRAPPER_HTML = """
<!DOCTYPE html>
<html>
<head><title>File Viewer</title></head>
<body>
    <div id="turnstile-wrapper">
        <p>Verify you are human</p>
    </div>
</body>
</html>
"""

# Normal download page HTML (no challenge)
NORMAL_DOWNLOAD_HTML = """
<!DOCTYPE html>
<html>
<head><title>File Viewer</title></head>
<body>
    <div class="file-info">
        <a class="btn" href="https://thegumonmyshoe.me/b71/FrmLzfLKUHBWDTQfqaTZ.mp4?md5=abc123&expires=999">Download</a>
    </div>
</body>
</html>
"""


def test_check_turnstile_detects_challenge_script() -> None:
    """Turnstile challenge with script tag should raise DDOSGuardError."""
    soup = BeautifulSoup(TURNSTILE_CHALLENGE_HTML, "html.parser")
    with pytest.raises(DDOSGuardError, match="Cloudflare Turnstile challenge detected"):
        _check_turnstile(soup)


def test_check_turnstile_detects_cf_turnstile_element() -> None:
    """Turnstile challenge with cf-turnstile element should raise DDOSGuardError."""
    # HTML with only the cf-turnstile element, no script tag
    html = """
    <html><body>
        <div class="cf-turnstile" data-sitekey="test"></div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    with pytest.raises(DDOSGuardError):
        _check_turnstile(soup)


def test_check_turnstile_detects_wrapper_element() -> None:
    """Turnstile challenge with #turnstile-wrapper should raise DDOSGuardError."""
    soup = BeautifulSoup(TURNSTILE_WRAPPER_HTML, "html.parser")
    with pytest.raises(DDOSGuardError):
        _check_turnstile(soup)


def test_check_turnstile_allows_normal_page() -> None:
    """Normal download page should NOT raise DDOSGuardError."""
    soup = BeautifulSoup(NORMAL_DOWNLOAD_HTML, "html.parser")
    # Should not raise - returns None
    _check_turnstile(soup)


def test_check_turnstile_allows_empty_page() -> None:
    """Empty/minimal HTML should NOT raise DDOSGuardError."""
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    _check_turnstile(soup)
