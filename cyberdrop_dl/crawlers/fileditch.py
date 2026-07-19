from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
from typing import TYPE_CHECKING, ClassVar, Self, override

from cyberdrop_dl import multi_process
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, parse_url
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Iterator

    import bs4
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


_HOMEPAGE_CATCH_ALL = "/s21/FHVZKQyAZlIsrneDAsp.jpeg"


class FileditchCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": (
            "/file.php?f=<file_id>",
            "/beta123/<file_id>/<name>",
            "/temp/<file_id>/<name>",
            "/alpha7/<file_id>/<name>",
        )
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://fileditchfiles.me/")
    DOMAIN: ClassVar[str] = "fileditch"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_, _, *_]:
                return await self.file(scrape_item)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if url.name == "file.php" and (path := url.query.get("f")):
            return url.with_path(path)
        return url

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_pow_soup(scrape_item.url)
        if soup.select_one(".gone-path"):
            raise ScrapeError(410)
        src = _extract_dl_url(soup)
        if src.path == _HOMEPAGE_CATCH_ALL:
            raise ScrapeError(422)

        filename, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(src, scrape_item, filename, ext)

    async def request_pow_soup(self, url: AbsoluteHttpURL) -> bs4.BeautifulSoup:
        soup = await self.request_soup(url)
        if form := soup.select_one("form#pow-form"):
            pow = POW.parse(form)  # noqa: A001
            self.log.warning("Solving proof of work challenge for %s\n%s", url, pow)
            solution = await _solve_pow(pow)
            self.log.debug("Solved pow %s after %s seconds", pow.challenge, solution.elapsed)
            soup = await self.request_soup(
                url,
                "POST",
                headers={"Referer": str(url), "Origin": "https://fileditchfiles.me"},
                data={
                    "orig_ref": pow.orig_ref,
                    "pow_challenge": pow.challenge,
                    "pow_ts": pow.ts,
                    "pow_diff": pow.difficulty,
                    "pow_sig": pow.signature,
                    "pow_nonce": solution.value,
                },
            )
            if soup.select_one("form#pow-form"):
                raise ScrapeError(422, "Proof of work verification failed")
        return soup


@dataclasses.dataclass(slots=True)
class POW:
    orig_ref: str
    challenge: str
    ts: int
    difficulty: int
    signature: str

    def __iter__(self) -> Iterator[tuple[str, str | int]]:
        for field in dataclasses.fields(self):
            yield field.name, getattr(self, field.name)

    def __json__(self) -> dict[str, str | int]:
        return dict(self)

    @classmethod
    def parse(cls, form: bs4.Tag) -> Self:
        def get(name: str) -> str:
            name = name if "_" in name else f"pow_{name}"
            return css.select(form, f"input[name={name}]", "value")

        return cls(
            orig_ref=get("orig_ref"),
            challenge=get("challenge"),
            ts=int(get("ts")),
            difficulty=int(get("diff")),
            signature=get("sig"),
        )


def _pow_worker(worker_idx: int, _: int, challenge: str, difficulty: int) -> int | None:
    nonce = worker_idx * 15_000
    while True:
        checksum = hashlib.sha256(f"{challenge}:{nonce}".encode()).digest()
        if _is_valid_solution(checksum, difficulty):
            return nonce
        nonce += 1


def _is_valid_solution(digest: bytes, difficulty: int) -> bool:
    idx, rem = difficulty >> 3, difficulty & 7
    if idx and digest[:idx] != b"\x00" * idx:
        return False
    if rem:
        return (digest[idx] & (0xFF << (8 - rem) & 0xFF)) == 0
    return True


async def _solve_pow(pow: POW) -> multi_process.RaceResult[int]:  # noqa: A002
    try:
        return await asyncio.to_thread(multi_process.race, _pow_worker, pow.challenge, pow.difficulty)
    except TimeoutError:
        raise TimeoutError(
            f"Unable to solve pow {pow.challenge} after {multi_process._TIMEOUT.get()} seconds"
        ) from None


def _extract_dl_url(soup: BeautifulSoup) -> AbsoluteHttpURL:
    js_join = '].join("")'
    js_text = css.select_text(soup, f"script:-soup-contains-own('{js_join}')")
    array = extr_text(js_text, "= [", js_join)
    try:
        return _parse_url_parts(f"[{array}]")
    except ValueError as e:
        raise ScrapeError(422, "Unable to extract download URL") from e


def _parse_url_parts(js_array: str) -> AbsoluteHttpURL:
    parts: list[str] = json.loads(js_array)
    url = parse_url("".join(parts), trim=False)
    if not (url.query.get("md5") and url.query.get("expires")):
        raise ValueError(url)
    return url
