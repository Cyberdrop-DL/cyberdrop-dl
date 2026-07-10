from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


class MonstercatCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Release": "/release/<slug>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.monstercat.com")
    DOMAIN: ClassVar[str] = "monstercat"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["release", release_slug]:
                return await self.release(scrape_item, release_slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def release(self, scrape_item: ScrapeItem, release_slug: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        name, release_date = _extract_info(soup)
        scrape_item.uploaded_at = self.parse_date(release_date, "%B %d, %Y")
        scrape_item.setup_as_album(self.create_title(name, release_slug), album_id=release_slug)
        downloaded = await self.get_album_results(release_slug)
        for track in _extract_tracks(soup):
            if self.check_album_results(track.url, downloaded):
                continue
            self.create_eager_task(self._track(scrape_item, track))
            scrape_item.add_children()

    async def _track(self, scrape_item: ScrapeItem, track: Track) -> None:
        with self.catch_errors(track.url):
            filename = self.create_custom_filename(track.name, ext := ".mp3")
            await self.handle_file(track.url, scrape_item, track.name, ext, custom_filename=filename)


@dataclasses.dataclass(slots=True)
class Track:
    id: str
    release_id: str
    name: str
    url: AbsoluteHttpURL


def _extract_tracks(soup: BeautifulSoup) -> Generator[Track]:
    for tr in css.iselect(soup, "table tr"):
        btn = css.select(tr, ".btn-play")
        release_id = css.attr(btn, "data-release-id")
        track_id = css.attr(btn, "data-track-id")
        name = css.select_text(tr, ".d-inline-flex.flex-column", decompose="span")
        url = MonstercatCrawler.PRIMARY_URL / "api/release" / release_id / "track-stream" / track_id
        yield Track(track_id, release_id, name, url)


def _extract_info(soup: BeautifulSoup) -> tuple[str, str]:
    name = css.select_text(soup, "h1")
    released = css.select_text(soup, "#content p.font-italic.mb-medium:-soup-contains-own(Released)")
    release_date = released.partition("Released ")[-1].strip()
    return name, release_date
