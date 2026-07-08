from __future__ import annotations

import asyncio
import logging
import sys
import time
from http.cookiejar import Cookie, MozillaCookieJar
from http.cookies import CookieError, SimpleCookie
from typing import TYPE_CHECKING

from cyberdrop_dl import aio

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Sequence
    from pathlib import Path


if sys.version_info < (3, 14):
    from http import cookies

    # https://github.com/python/cpython/issues/112713
    cookies.Morsel._reserved["partitioned"] = "partitioned"  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
    cookies.Morsel._flags.add("partitioned")  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]


logger = logging.getLogger(__name__)


async def read_netscape_files(cookie_files: Sequence[Path]) -> AsyncGenerator[SimpleCookie]:
    now = int(time.time())
    all_domains: set[str] = set()
    duplicates: set[str] = set()
    for cookie_jar in await aio.gather(*(asyncio.to_thread(_read_netscape_file, file) for file in cookie_files)):
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

        try:
            yield domain, make_simple_cookie(cookie, now)
        except (CookieError, ValueError) as e:
            logger.error(f"Unable to parse cookie '{cookie.name}' from domain {cookie.domain} ({e!r})")


def _read_netscape_file(file: Path) -> MozillaCookieJar | None:
    cookie_jar = MozillaCookieJar(file)
    try:
        cookie_jar.load(ignore_discard=True)
    except OSError as e:
        logger.error(f"Unable to load cookies from '{file.name}':\n  {e!s}")
    else:
        return cookie_jar


def make_simple_cookie(cookie: Cookie, now: float) -> SimpleCookie:
    simple_cookie = SimpleCookie()
    assert cookie.value is not None
    simple_cookie[cookie.name] = cookie.value
    morsel = simple_cookie[cookie.name]
    morsel["domain"] = cookie.domain
    morsel["path"] = cookie.path
    morsel["secure"] = cookie.secure
    if cookie.expires:
        morsel["max-age"] = str(max(0, cookie.expires - int(now)))
    else:
        morsel["max-age"] = ""
    return simple_cookie
