from __future__ import annotations

import dataclasses
import itertools
import re
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text

if TYPE_CHECKING:
    from collections.abc import Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem

_find_http_urls = re.compile(r"(?:http(?!.*\.\.)[^ ]*?)(?=($|\n|\r\n|\r|\s|\"|\[/URL]|']\[|]\[|\[/img]|</|'))").finditer


@dataclasses.dataclass(slots=True)
class Post:
    date: str
    model: str
    content: str
    title: str
    images: tuple[str, ...]
    videos: tuple[str, ...]


class CoomerFansCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/p/<post_id>/<user_id>/<service>",
    }

    DOMAIN: ClassVar[str] = "coomerfans"
    FOLDER_DOMAIN: ClassVar[str] = "CoomerFans"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://coomerfans.com")
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date} - {title}"

    @property
    def ignore_content(self) -> bool:
        return self.manager.config.settings.ignore_options.ignore_coomer_post_content

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["p", post_id, user_id, _]:
                return await self.post(scrape_item, post_id, user_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str, user_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        post = _parse_post(soup)
        title = self.create_title(post.model, user_id)
        scrape_item.setup_as_album(title, album_id=user_id)
        scrape_item.uploaded_at = date = self.parse_iso_date(post.date)
        post_title = self.create_separate_post_title(post.title, post_id, date)
        scrape_item.add_to_parent_title(post_title)

    def _post(self, scrape_item: ScrapeItem, post: Post) -> None:
        seen: set[str] = set()
        for url in itertools.chain(post.images, post.videos):
            if url not in seen:
                seen.add(url)
                self.create_task(self.direct_file(scrape_item, self.parse_url(url)))
                scrape_item.add_children()

        self._handle_post_content(scrape_item, post)

    def _handle_post_content(self, scrape_item: ScrapeItem, post: Post) -> None:
        """Gets links out of content in post and sends them to a new crawler."""
        if not post.content or self.ignore_content:
            return

        for url in self.__parse_content_urls(post):
            new_scrape_item = scrape_item.create_child(url)
            self.handle_external_links(new_scrape_item)
            scrape_item.add_children()

    def __parse_content_urls(self, post: Post) -> Generator[AbsoluteHttpURL]:
        seen: set[str] = set()
        for match in _find_http_urls(post.content):
            if (link := match.group().replace(".md.", ".")) not in seen:
                seen.add(link)
                try:
                    url = self.parse_url(link)
                except Exception:
                    pass
                else:
                    if self.DOMAIN not in url.host:
                        yield url


def _parse_post(soup: BeautifulSoup) -> Post:
    main = css.select(soup, "main.content")
    body = css.select(main, ".post-body")

    def get(attr: str) -> str:
        return css.select_text(main, attr)

    return Post(
        title=get("h1"),
        model=get(".model-name"),
        content=get(".post-date + p"),
        date=extr_text(get(".post-date"), "Added ", " +"),
        images=tuple(css.iselect(body, "img", "src")),
        videos=tuple(css.iselect(body, "source", "src")),
    )
