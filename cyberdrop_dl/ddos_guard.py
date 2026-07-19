from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
from typing import TYPE_CHECKING, Protocol, final, override

import yarl
from bs4 import BeautifulSoup

from cyberdrop_dl import multi_process
from cyberdrop_dl.exceptions import DDOSGuardError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from multidict import MultiMapping


class _Response(Protocol):
    @property
    def content_type(self) -> str: ...
    @property
    def headers(self) -> MultiMapping[str]: ...
    @property
    def status(self) -> int: ...
    async def text(self) -> str: ...


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


async def check_resp(resp: _Response, /) -> None:
    if "html" not in resp.content_type:
        return

    mitigations: list[type[DDosGuard]] = []
    for cls in _ALL_PROTECTIONS:
        if not cls.may_be_challenge(resp):
            continue
        if cls._is_challenge(resp):
            raise DDOSGuardError(f"{cls.__name__} anti-bot protection detected")
        mitigations.append(cls)

    if not mitigations:
        return

    soup = _soup(await resp.text())
    check_soup(soup, mitigations)


def check_html(html: str) -> None:
    check_soup(_soup(html))


def check_soup(soup: BeautifulSoup, /, posibilities: Iterable[type[DDosGuard]] | None = None) -> None:
    if posibilities is None:
        posibilities = _ALL_PROTECTIONS
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

    def __init_subclass__(cls) -> None:
        _ALL_PROTECTIONS.append(cls)

    @classmethod
    def may_be_challenge(cls, resp: _Response) -> bool:
        server = resp.headers.get("server")
        return bool(server and server.casefold().startswith("ddos-guard"))

    @final
    @classmethod
    def is_confirmed_challenge(cls, resp: _Response) -> bool:
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


_ALL_PROTECTIONS = [DDosGuard]


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


class BasedFlare(DDosGuard):
    # TODO: add logic to solve it: https://gitgud.io/fatchan/haproxy-protection/-/blob/71015f402c49afcdcb3e70bc98dbaddc5ccbc74c/src/js/ch.js#L105
    TITLES = ("Hold on...",)
    SELECTOR = ", ".join(("head[data-langjson*='Performance & security by BasedFlare']", "body[data-pow][data-mode]"))

    @classmethod
    @override
    def check(cls, soup: BeautifulSoup) -> bool:
        return bool(soup.select_one(cls.SELECTOR))


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
    def _solve(cls, challenge: _AnubisChallenge, *, timeout: float = 30.0) -> _AnubisSolution:
        try:
            with multi_process.ctx(timeout=timeout):
                result = multi_process.race(_anubis_worker, challenge.data, challenge.difficulty)
        except TimeoutError:
            msg = f"Unable to solve Anubis challenge after {timeout:0.2f} seconds: {challenge}"
            raise DDOSGuardError(msg) from None

        nonce, checksum = result.value
        return _AnubisSolution(challenge.id, nonce, checksum, challenge.difficulty, result.elapsed)


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
