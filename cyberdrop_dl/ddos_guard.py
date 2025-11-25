import dataclasses
import hashlib
import json
from typing import Any, Protocol

import yarl
from bs4 import BeautifulSoup

from cyberdrop_dl.exceptions import DDOSGuardError

__all__ = ["check"]


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

    for protection in (_DDosGuard, _CloudflareTurnstile, _Anubis):
        if protection.check(soup):
            raise DDOSGuardError(f"{protection.__name__.removeprefix('_')} detected")


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


@dataclasses.dataclass(slots=True, frozen=True)
class AnubisSolution:
    id: str
    nonce: int
    hash: str
    workers: int
    difficulty: int
    total_time: float

    @property
    def url(self) -> yarl.URL:
        # this URl is relative to the origin url
        return yarl.URL("/anubis/api/pass-challenge").with_query(
            id=self.id,
            response=self.hash,
            nonce=self.nonce,
            elapsedTime=int(self.total_time * 1000),
        )


class _Anubis(_DDosGuard):
    TITLES = "Making sure you're not a bot!"
    CHALLENGE = "script#anubis_challenge:-soup-contains(algorithm)"
    SELECTOR = ", ".join(
        (
            CHALLENGE,
            "p:-soup-contains-own(the administrator of this website has set up Anubis to protect the server against the scourge of AI)",
        ),
    )

    @classmethod
    def parse_challenge(cls, soup: BeautifulSoup) -> dict[str, Any] | None:
        if script := soup.select_one(cls.CHALLENGE):
            return json.loads(script.get_text(strip=True))

    @classmethod
    def solve(cls, id: str, challenge: str, difficulty: int, timeout: int | None = 30) -> AnubisSolution | None:
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
                        return AnubisSolution(id, nonce, hash, max_workers, difficulty, elapsed)

            except TimeoutError:
                return None


def _anubis_worker(start: int, step: int, challenge: str, difficulty: int) -> tuple[int, str] | None:
    nonce = start
    target = "0" * difficulty
    while True:
        hash = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
        if hash.startswith(target):
            return nonce, hash
        nonce += step


def _main() -> None:
    html = """<!doctype html>
        <html lang="en">
        <head>
            <title>Making sure you&#39;re not a bot!</title>
            <script id="anubis_version" type="application/json">"v1.23.0"</script><script id="anubis_challenge" type="application/json">{"rules":{"algorithm":"fast","difficulty":5,"report_as":5},"challenge":{"id":"019abb13-2859-7587-bec3-16e0a3f67ce9","method":"fast","randomData":"1b7a4c4a35a9e11ac23c2ae78845476ed627d1f36c8c27c1b3386d7c6f997c2f803fbfd3884b9b51642859e02537a62b9032b8b58b38d4af400aa62c8293ba85","issuedAt":"2025-11-25T12:53:06.265369852Z","metadata":{"User-Agent":"Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0","X-Real-Ip":"192.168.100.174"},"spent":false}}</script><script id="anubis_base_prefix" type="application/json">""</script><script id="anubis_public_url" type="application/json">""</script>
        </head>
        <body id="top">
            <main>
                <h1 id="title" class="centered-div">Making sure you&#39;re not a bot!</h1>
                <div class="centered-div">
                    <img id="image" style="width:100%;max-width:256px;" src="/.within.website/x/cmd/anubis/static/img/pensive.webp?cacheBuster=v1.23.0"> <img style="display:none;" style="width:100%;max-width:256px;" src="/.within.website/x/cmd/anubis/static/img/happy.webp?cacheBuster=v1.23.0">
                    <p id="status">Loading...</p>
                    <script async type="module" src="/.within.website/x/cmd/anubis/static/js/main.mjs?cacheBuster=v1.23.0"></script>
                    <div id="progress" role="progressbar" aria-labelledby="status">
                    <div class="bar-inner"></div>
                    </div>
                    <details>
                    <p>You are seeing this because the administrator of this website has set up Anubis to protect the server against the scourge of AI companies aggressively scraping websites. This can and does cause downtime for the websites, which makes their resources inaccessible for everyone.</p>
                    <p>Anubis is a compromise. Anubis uses a Proof-of-Work scheme in the vein of Hashcash, a proposed proof-of-work scheme for reducing email spam. The idea is that at individual scales the additional load is ignorable, but at mass scraper levels it adds up and makes scraping much more expensive.</p>
                    <p>Ultimately, this is a placeholder solution so that more time can be spent on fingerprinting and identifying headless browsers (EG: via how they do font rendering) so that the challenge proof of work page doesn&#39;t need to be presented to users that are much more likely to be legitimate.</p>
                    <p>Please note that Anubis requires the use of modern JavaScript features that plugins like JShelter will disable. Please disable JShelter or other such plugins for this domain.</p>
                    </details>
                </footer>
            </main>
        </body>
        </html>
        """

    soup = BeautifulSoup(html, "html.parser")
    assert _Anubis.check(soup)
    anubis = _Anubis.parse_challenge(soup)
    assert anubis
    difficulty: int = anubis["rules"]["difficulty"]
    challenge: str = anubis["challenge"]["randomData"]
    challenge_id: str = anubis["challenge"]["id"]
    solution = _Anubis.solve(challenge_id, challenge, difficulty)
    assert solution

    print("Result:", solution)  # noqa: T201


if __name__ == "__main__":
    _main()
