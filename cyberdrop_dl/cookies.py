from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from http.cookiejar import Cookie, CookieJar, MozillaCookieJar
from http.cookies import CookieError, SimpleCookie
from typing import TYPE_CHECKING, Final

from cyberdrop_dl.dependencies import browser_cookie3

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Sequence
    from pathlib import Path

    from cyberdrop_dl.constants import Browser


if sys.version_info < (3, 14):
    from http import cookies

    # https://github.com/python/cpython/issues/112713
    cookies.Morsel._reserved["partitioned"] = "partitioned"  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
    cookies.Morsel._flags.add("partitioned")  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]


logger = logging.getLogger(__name__)


_COOKIE_EXTRACTORS: Final = {func.__name__: func for func in browser_cookie3.all_browsers}
_CHROMIUM_BROWSERS = frozenset(
    (
        "chrome",
        "chromium",
        "opera",
        "opera_gx",
        "brave",
        "edge",
        "vivaldi",
        "arc",
    )
)


async def extract_cookies(browser: Browser) -> CookieJar:
    extract = _COOKIE_EXTRACTORS[browser]
    try:
        data = await asyncio.to_thread(extract)
        return data

    except PermissionError as e:
        msg = (
            "We've encountered a Permissions Error. Please close all browsers and try again\n"
            "If you are still having issues, make sure all browsers processes are closed in Task Manager\n"
            f"ERROR: {e!s}"
        )

    except ValueError as e:
        msg = f"ERROR: {e!s}"

    except browser_cookie3.BrowserCookieError as e:
        if (
            "Unable to get key for cookie decryption" in (msg := str(e))
            and browser in _CHROMIUM_BROWSERS
            and os.name == "nt"
        ):
            msg = f"ERROR: Cookie extraction from {browser.capitalize()} is not supported on Windows - {msg}"

        else:
            msg = (
                "Browser extraction ran into an error, the selected browser may not be available on your system\n"
                "If you are still having issues, make sure all browsers processes are closed in Task Manager.\n"
                f"ERROR: {e!s}"
            )

    raise browser_cookie3.BrowserCookieError(f"{msg}\n\nNothing has been saved.")


def split_cookies(extracted_cookies: CookieJar) -> dict[str, MozillaCookieJar]:
    cookie_jars: dict[str, MozillaCookieJar] = {}
    for cookie in extracted_cookies:
        domain = cookie.domain.lstrip(".").removeprefix("www.")
        cookie_jars.setdefault(domain, MozillaCookieJar()).set_cookie(cookie)
    return cookie_jars


async def export_cookies(cookies: CookieJar, output_path: Path) -> None:
    cookie_jars = split_cookies(cookies)
    await asyncio.to_thread(output_path.mkdir, parents=True, exist_ok=True)
    _ = await asyncio.gather(
        *(
            asyncio.to_thread(
                cj.save,
                str(output_path / f"{domain}.txt"),
                ignore_discard=True,
                ignore_expires=True,
            )
            for domain, cj in cookie_jars.items()
        )
    )


async def read_netscape_files(cookie_files: Sequence[Path]) -> AsyncGenerator[SimpleCookie]:
    now = int(time.time())
    all_domains: set[str] = set()
    duplicates: set[str] = set()
    for cookie_jar in await asyncio.gather(*(asyncio.to_thread(_read_netscape_file, file) for file in cookie_files)):
        if not cookie_jar:
            continue

        domains_here: set[str] = set()
        for domain, cookie in _parse_cookie_jar(cookie_jar, now):
            domains_here.add(domain)
            yield cookie

        duplicates.update(all_domains.intersection(domains_here))
        all_domains.update(domains_here)

    for domain in sorted(duplicates):
        msg = (
            f"Found cookies for {domain} in more than one file; "
            "The value from the last parsed file will be used in case of cookie name collisions"
        )
        logger.warning(msg)


def _parse_cookie_jar(cookie_jar: MozillaCookieJar, now: int) -> Generator[tuple[str, SimpleCookie]]:

    domains: set[str] = set()
    has_expired_cookies: set[str] = set()
    for cookie in cookie_jar:
        if not cookie.value:
            continue

        domain = cookie.domain.lstrip(".").removeprefix("www.")
        if domain not in domains:
            logger.info(f"Found cookies for {domain} in {cookie_jar.filename}")
            domains.add(domain)

        if (domain not in has_expired_cookies) and cookie.is_expired(now):
            has_expired_cookies.add(domain)
            logger.warning(f"Cookies for {domain} are expired")

        yield domain, make_simple_cookie(cookie, now)


def _read_netscape_file(file: Path) -> MozillaCookieJar | None:
    cookie_jar = MozillaCookieJar(file)
    try:
        cookie_jar.load(ignore_discard=True)
        return cookie_jar
    except OSError as e:
        logger.error(f"Unable to load cookies from '{file.name}':\n  {e!s}")


def make_simple_cookie(cookie: Cookie, now: float) -> SimpleCookie:
    simple_cookie = SimpleCookie()
    assert cookie.value is not None

    try:
        simple_cookie[cookie.name] = cookie.value
    except CookieError:
        return SimpleCookie()

    morsel = simple_cookie[cookie.name]
    morsel["domain"] = cookie.domain
    morsel["path"] = cookie.path
    morsel["secure"] = cookie.secure
    if cookie.expires:
        morsel["max-age"] = str(max(0, cookie.expires - int(now)))
    else:
        morsel["max-age"] = ""
    return simple_cookie
