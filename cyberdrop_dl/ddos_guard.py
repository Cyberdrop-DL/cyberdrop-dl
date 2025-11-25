from typing import Protocol

from bs4 import BeautifulSoup

from cyberdrop_dl.exceptions import DDOSGuardError


class _DDosGuard:
    TITLES = "Just a moment...", "DDoS-Guard"
    SELECTOR = ", ".join(
        (
            "#cf-challenge-running",
            ".ray_id",
            ".attack-box",
            "#cf-please-wait",
            "#challenge-spinner",
            "#trk_jschal_js",
            "#turnstile-wrapper",
            ".lds-ring",
        )
    )

    @classmethod
    def check(cls, soup: BeautifulSoup) -> bool:
        if (title := soup.select_one("title")) and (title_str := title.string):
            if any(title.casefold() == title_str.casefold() for title in cls.TITLES):
                return True

        return bool(soup.select_one(cls.SELECTOR))


class _CloudflareTurnstile(_DDosGuard):
    TITLES = "Simpcity Cuck Detection", "Attention Required! | Cloudflare", "Sentinel CAPTCHA"
    SELECTOR = ", ".join(
        (
            "captchawrapper",
            "cf-turnstile",
            "script[src*='challenges.cloudflare.com/turnstile']",
            "script:-soup-contains('Dont open Developer Tools')",
        )
    )


class _Response(Protocol):
    @property
    def content_type(self) -> str: ...
    async def text(self) -> str: ...


async def check(content: _Response | str, /) -> BeautifulSoup | None:
    if isinstance(content, str):
        soup = BeautifulSoup(content, "html.parser")

    elif "html" not in content.content_type:
        return

    else:
        try:
            soup = BeautifulSoup(await content.text(), "html.parser")
        except UnicodeDecodeError:
            return

    if _DDosGuard.check(soup) or _CloudflareTurnstile.check(soup):
        raise DDOSGuardError


__all__ = ["check"]
