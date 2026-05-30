from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import os
import sys
from typing import TYPE_CHECKING, Protocol, final

import yarl
from bs4 import BeautifulSoup
from typing_extensions import override

from cyberdrop_dl.exceptions import DDOSGuardError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from multidict import MultiDict


class _Response(Protocol):
    @property
    def content_type(self) -> str: ...
    @property
    def headers(self) -> MultiDict[str]: ...
    @property
    def status_code(self) -> int: ...
    async def text(self) -> str: ...


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


async def check_resp(resp: _Response, /) -> None:
    if "html" not in resp.content_type:
        return

    posibilities = [cls for cls in (DDosGuard, CloudFlareTurnstile, Anubis) if cls.may_be_challenge(resp)]
    if not posibilities:
        return

    for protection in posibilities:
        if protection._is_challenge(resp):  # pyright: ignore[reportPrivateUsage]
            raise DDOSGuardError(f"{protection.__name__} anti-bot protection detected")

    soup = _soup(await resp.text())
    check_soup(soup, posibilities)


def check_html(html: str) -> None:
    check_soup(_soup(html))


def check_soup(soup: BeautifulSoup, /, posibilities: Iterable[type[DDosGuard]] | None = None) -> None:
    if posibilities is None:
        posibilities = (DDosGuard, CloudFlareTurnstile, Anubis)
    for protection in posibilities:
        if protection.check(soup):
            raise DDOSGuardError(f"{protection.__name__} anti-bot protection detected")


class DDosGuard:
    TITLES = "Just a moment...", "DDoS-Guard"
    SELECTOR = ", ".join(
        (
            "#ddg-captcha",
            "#challenge-spinner",
            "#trk_jschal_js",
            "#turnstile-wrapper",
        )
    )

    @classmethod
    def may_be_challenge(cls, resp: _Response) -> bool:
        server = resp.headers.get("server")
        return bool(server and server.casefold().startswith("ddos-guard"))

    @final
    @classmethod
    def is_challenge(cls, resp: _Response) -> bool:
        return cls.may_be_challenge(resp) and cls._is_challenge(resp)

    @classmethod
    def _is_challenge(cls, resp: _Response) -> bool:
        assert resp is not None
        return False

    @classmethod
    def check(cls, soup: BeautifulSoup) -> bool:
        if (
            (title := soup.select_one("title"))
            and (title_str := title.string)
            and any(title.casefold() == title_str.casefold() for title in cls.TITLES)
        ):
            return True

        return bool(soup.select_one(cls.SELECTOR))


class CloudFlareTurnstile(DDosGuard):
    TITLES = "Simpcity Cuck Detection", "Attention Required! | Cloudflare", "Sentinel CAPTCHA"
    SELECTOR = ", ".join(
        (
            "captchawrapper",
            "cf-turnstile",
            "#cf-challenge-running",
            "#cf-please-wait",
            "iframe[id^='cf-chl-']",
            "iframe script:-soup-contains('_cf_chl_opt')",
            "script:-soup-contains('Dont open Developer Tools')",
        )
    )

    @classmethod
    @override
    def may_be_challenge(cls, resp: _Response) -> bool:
        server = resp.headers.get("server")
        return bool(server and server.casefold().startswith("cloudflare"))

    @classmethod
    @override
    def _is_challenge(cls, resp: _Response) -> bool:
        mitigated = resp.headers.get("cf-mitigated")
        return bool(mitigated and mitigated.casefold() == "challenge")

    @classmethod
    @override
    def check(cls, soup: BeautifulSoup) -> bool:
        return super().check(soup) and bool(soup.select_one("script[src*='challenges.cloudflare.com/turnstile/v']"))


class Anubis(DDosGuard):
    TITLES = ("Making sure you're not a bot!",)
    CHALLENGE = "script#anubis_challenge:-soup-contains(algorithm)"
    SELECTOR = ", ".join(
        (
            CHALLENGE,
            "p:-soup-contains-own(the administrator of this website has set up Anubis to protect the server against the scourge of AI)",
        ),
    )

    @classmethod
    @override
    def may_be_challenge(cls, resp: _Response) -> bool:
        for cookie in resp.headers.getall("Set-Cookie", ()):
            if "-anubis-cookie-verification" in cookie or "-anubis-auth" in cookie:
                return True
        return False

    @classmethod
    def parse_challenge(cls, soup: BeautifulSoup) -> _AnubisChallenge | None:
        if script := soup.select_one(cls.CHALLENGE):
            anubis = json.loads(script.get_text(strip=True))
            return _AnubisChallenge(
                difficulty=anubis["rules"]["difficulty"],
                data=anubis["challenge"]["randomData"],
                id=anubis["challenge"]["id"],
            )

    @classmethod
    async def solve(cls, challenge: _AnubisChallenge) -> _AnubisSolution:
        return await asyncio.to_thread(cls._solve, challenge)

    @classmethod
    def _solve(cls, challenge: _AnubisChallenge, *, timeout: int | None = 30) -> _AnubisSolution:
        import multiprocessing as mp
        import time
        from concurrent.futures import ProcessPoolExecutor, as_completed

        max_workers = max(cpu_count() // 2, 1)
        start_time = time.monotonic()

        with ProcessPoolExecutor(max_workers=max_workers, mp_context=mp.get_context("spawn")) as executor:
            futures = [
                executor.submit(_anubis_worker, idx, max_workers, challenge.data, challenge.difficulty)
                for idx in range(max_workers)
            ]

            try:
                for future in as_completed(futures, timeout=timeout):
                    result = future.result()
                    if result is not None:
                        nonce, checksum = result
                        elapsed = time.monotonic() - start_time
                        executor.shutdown(wait=False, cancel_futures=True)
                        return _AnubisSolution(
                            challenge.id, nonce, checksum, challenge.difficulty, max_workers, elapsed
                        )

            except TimeoutError:
                pass

            elapsed = time.monotonic() - start_time
            raise DDOSGuardError(f"Unable to solve challenge after {elapsed:0.2f} seconds: {challenge}")


@dataclasses.dataclass(slots=True, frozen=True)
class _AnubisChallenge:
    id: str
    data: str
    difficulty: int


@dataclasses.dataclass(slots=True, frozen=True)
class _AnubisSolution:
    id: str
    nonce: int
    hash: str
    difficulty: int
    workers: int = dataclasses.field(compare=False)
    total_time: float = dataclasses.field(compare=False)

    @property
    def url(self) -> yarl.URL:
        # this URl is relative to the origin url
        return yarl.URL("/.within.website/x/cmd/anubis/api/pass-challenge").with_query(
            id=self.id,
            response=self.hash,
            nonce=self.nonce,
            elapsedTime=int(self.total_time * 1000),
        )


def _anubis_worker(start: int, step: int, challenge: str, difficulty: int) -> tuple[int, str] | None:
    nonce = start
    target = "0" * difficulty
    while True:
        checksum = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
        if checksum.startswith(target):
            return nonce, checksum
        nonce += step


if sys.platform not in {"win32", "darwin"} and hasattr(os, "sched_getaffinity"):

    def cpu_count() -> int:
        return len(os.sched_getaffinity(0))


else:

    def cpu_count() -> int:
        return os.cpu_count() or 1
