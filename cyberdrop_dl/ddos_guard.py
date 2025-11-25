from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Protocol

import yarl
from bs4 import BeautifulSoup

from cyberdrop_dl.exceptions import DDOSGuardError

__all__ = ["check"]


class _Response(Protocol):
    @property
    def content_type(self) -> str: ...
    async def text(self) -> str: ...


async def check(content: _Response | str, /) -> None:
    if isinstance(content, str):
        soup = BeautifulSoup(content, "html.parser")

    elif "html" not in content.content_type:
        return

    else:
        try:
            soup = BeautifulSoup(await content.text(), "html.parser")
        except UnicodeDecodeError:
            return

    for protection in (DDosGuard, CloudFlareTurnstile, Anubis):
        if protection.check(soup):
            raise DDOSGuardError(f"{protection.__name__} anti-bot protection detected")


class DDosGuard:
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


class CloudFlareTurnstile(DDosGuard):
    TITLES = "Simpcity Cuck Detection", "Attention Required! | Cloudflare", "Sentinel CAPTCHA"
    SELECTOR = ", ".join(
        (
            "captchawrapper",
            "cf-turnstile",
            "script[src*='challenges.cloudflare.com/turnstile']",
            "script:-soup-contains('Dont open Developer Tools')",
        )
    )


class Anubis(DDosGuard):
    TITLES = "Making sure you're not a bot!"
    CHALLENGE = "script#anubis_challenge:-soup-contains(algorithm)"
    SELECTOR = ", ".join(
        (
            CHALLENGE,
            "p:-soup-contains-own(the administrator of this website has set up Anubis to protect the server against the scourge of AI)",
        ),
    )

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
    def solve(cls, id: str, challenge: str, difficulty: int, *, timeout: int | None = 30) -> _AnubisSolution | None:
        import os
        import time
        from concurrent.futures import ProcessPoolExecutor, as_completed

        max_workers = (os.process_cpu_count() or 1) // 2
        start_time = time.monotonic()

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(_anubis_worker, idx, max_workers, challenge, difficulty) for idx in range(max_workers)
            ]

            try:
                for future in as_completed(futures, timeout=timeout):
                    result = future.result()
                    if result is not None:
                        nonce, hash = result
                        elapsed = time.monotonic() - start_time
                        executor.shutdown(wait=False, cancel_futures=True)
                        return _AnubisSolution(id, nonce, hash, max_workers, difficulty, elapsed)

            except TimeoutError:
                return None


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
    workers: int
    difficulty: int
    total_time: float = dataclasses.field(compare=False)

    @property
    def url(self) -> yarl.URL:
        # this URl is relative to the origin url
        return yarl.URL("/anubis/api/pass-challenge").with_query(
            id=self.id,
            response=self.hash,
            nonce=self.nonce,
            elapsedTime=int(self.total_time * 1000),
        )


def _anubis_worker(start: int, step: int, challenge: str, difficulty: int) -> tuple[int, str] | None:
    nonce = start
    target = "0" * difficulty
    while True:
        hash = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
        if hash.startswith(target):
            return nonce, hash
        nonce += step
