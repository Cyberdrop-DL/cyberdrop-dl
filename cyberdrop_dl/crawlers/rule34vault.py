from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    CONTENT = "div[class='box-grid ng-star-inserted'] a[class='box ng-star-inserted']"
    TITLE = "div[class*=title]"
    DATE = 'div[class="posted-date-full text-secondary mt-4 ng-star-inserted"]'
    VIDEO = 'div[class="con-video ng-star-inserted"] > video > source'
    IMAGE = 'img[class*="img ng-star-inserted"]'


PRIMARY_URL = AbsoluteHttpURL("https://rule34vault.com")
_PER_PAGE = 100


class Rule34VaultCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/post/...",
        "Playlist": "/playlists/view/...",
        "Tag": "/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "rule34vault"
    FOLDER_DOMAIN: ClassVar[str] = "Rule34Vault"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["post", post_id]:
                return await self.file(scrape_item, post_id)
            case ["playlists", playlist_id]:
                return await self.playlist(scrape_item, playlist_id)
            case [tag]:
                return await self.tags(scrape_item, tag)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, playlist_id: str) -> None:
        init_page = int(scrape_item.url.query.get("page") or 1)
        title: str = ""
        for page in itertools.count(init_page):
            url = scrape_item.url.with_query(page=page)
            n_images = 0
            soup = await self.request_soup(url)

            if not title:
                title_str: str = css.select_text(soup, Selector.TITLE)
                title = self.create_title(title_str, playlist_id)
                scrape_item.setup_as_album(title, album_id=playlist_id)

            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.CONTENT):
                n_images += 1
                self.create_task(self.run(new_scrape_item))

            if n_images < 30:
                break

    @error_handling_wrapper
    async def tags(self, scrape_item: ScrapeItem, tag: str) -> None:
        init_page = int(scrape_item.url.query.get("page") or 1)
        title = self.create_title(tag)
        scrape_item.setup_as_album(title)

        for page in itertools.count(init_page):
            soup = await self.request_soup(scrape_item.url.with_query(page=page))

            n_images = 0
            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.CONTENT):
                n_images += 1
                self.create_task(self.run(new_scrape_item))

            if n_images < 30:
                break

    async def _api_pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[list[dict[str, Any]]]:
        params = {"CountTotal": False, "Skip": 0}
        while True:
            resp = await self.request_json(url, method="POST", json=params)
            yield resp["items"]

            if len(resp["items"]) < _PER_PAGE:
                return

            params["cursor"] = resp.get("cursor")
            params["Skip"] += params["take"]

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, post_id: str) -> None:
        canonical_url = scrape_item.url.with_query(None)
        if await self.check_complete_from_referer(canonical_url):
            return

        post: dict[str, Any] = await self.request_json(self.PRIMARY_URL / "api/v2/post" / post_id)
        scrape_item.uploaded_at = self.parse_iso_date(post["created"])
        scrape_item.url = canonical_url
        src = _create_src_url(post)
        await self.direct_file(scrape_item, src)


def _create_src_url(post: dict[str, Any]) -> AbsoluteHttpURL:
    post_id = int(post["id"])
    ext = "jpg" if post["type"] == 0 else "mp4"
    return PRIMARY_URL / f"posts/{post_id // 1000}/{post_id}/{post_id}.{ext}"
