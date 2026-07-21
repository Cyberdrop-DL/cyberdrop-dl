from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
from typing import TYPE_CHECKING, ClassVar, Self, override

from cyberdrop_dl import multi_process
from cyberdrop_dl.crawlers import Registry
from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, parse_url
from cyberdrop_dl.utils.dataclass import DictDataclass
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    import bs4

    from cyberdrop_dl.url_objects import ScrapeItem


_HOMEPAGE_CATCH_ALL = "/s21/FHVZKQyAZlIsrneDAsp.jpeg"


@Registry.database.fix_referer
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
    _RATE_LIMIT: ClassVar[RateLimit] = 3, 1

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

    async def _solve_pow(self, url: AbsoluteHttpURL, pow: ProofOfWork) -> int:  # noqa: A002
        try:
            async with self._startup_lock:
                self.log.warning("Solving proof of work challenge for %s\n%s", url, dict(pow))
                solution = await asyncio.to_thread(multi_process.race, _pow_worker, pow.pow_challenge, pow.pow_diff)

        except TimeoutError:
            msg = f"Unable to solve challenge {pow.pow_challenge} after {multi_process.TIMEOUT.get()} seconds"
            raise TimeoutError(msg) from None

        self.log.debug("Solved pow %s after %s seconds", pow.pow_challenge, solution.elapsed)
        return solution.value

    async def request_pow_soup(self, url: AbsoluteHttpURL) -> bs4.BeautifulSoup:
        soup = await self.request_soup(url)
        if form := soup.select_one("form#pow-form"):
            pow = ProofOfWork.parse(form)  # noqa: A001
            nonce = await self._solve_pow(url, pow)
            soup = await self.request_soup(
                url,
                "POST",
                headers={"Referer": str(url), "Origin": "https://fileditchfiles.me"},
                data=dict(pow) | {"pow_nonce": nonce},
            )
            if soup.select_one("form#pow-form"):
                raise ScrapeError(422, "Proof of work verification failed")
        return soup


@dataclasses.dataclass(slots=True)
class ProofOfWork(DictDataclass):
    orig_ref: str
    pow_challenge: str
    pow_ts: int
    pow_diff: int
    pow_sig: str

    def __post_init__(self) -> None:
        self.pow_ts = int(self.pow_ts)
        self.pow_diff = int(self.pow_diff)

    @classmethod
    def parse(cls, form: bs4.Tag) -> Self:
        def inputs():
            for field in css.iselect(form, "input[name]"):
                yield css.attr(field, "name"), css.attr(field, "value")

        return cls.from_dict(dict(inputs()))


def _pow_worker(worker_idx: int, _: int, challenge: str, difficulty: int) -> int | None:
    nonce = worker_idx * 15_000
    while True:
        checksum = hashlib.sha256(f"{challenge}:{nonce}".encode()).digest()
        if _is_valid_solution(checksum, difficulty):
            return nonce
        nonce += 1


def _is_valid_solution(checksum: bytes, difficulty: int) -> bool:
    idx, rem = difficulty >> 3, difficulty & 7
    if idx and checksum[:idx] != b"\x00" * idx:
        return False
    if rem:
        return (checksum[idx] & (0xFF << (8 - rem) & 0xFF)) == 0
    return True


def _extract_dl_url(soup: bs4.BeautifulSoup) -> AbsoluteHttpURL:
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
