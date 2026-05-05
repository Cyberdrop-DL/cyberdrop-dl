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
    model_name: str
    content: str
    title: str
    images: tuple[str, ...]
    videos: tuple[str, ...]


class CoomerFansCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/p/<post_id>/...",
        "User": "/u/<user_id>/...",
        "**NOTE**": "`--ignore-coomer-post-content` affects this crawler. All other kemono config options are ignored",
    }

    DOMAIN: ClassVar[str] = "coomerfans"
    FOLDER_DOMAIN: ClassVar[str] = "CoomerFans"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://coomerfans.com")
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date} - {title}"
    NEXT_PAGE_SELECTOR: ClassVar[str] = ".pagination a.next"

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["p", _, *rest] | ["u", _, _, *rest] if not rest:
                return url / ""
            case _:
                return url

    @property
    def ignore_content(self) -> bool:
        return self.manager.config.settings.ignore_options.ignore_coomer_post_content

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["p", post_id, *_]:
                return await self.post(scrape_item, post_id)
            case ["u", _service, _user_id, *_]:
                return await self.profile(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        post = _parse_post(soup)
        scrape_item.setup_as_album(self.create_title(post.model_name))
        scrape_item.uploaded_at = date = self.parse_iso_date(post.date)
        post_title = self.create_separate_post_title(post.title, post_id, date)
        scrape_item.add_to_parent_title(post_title)
        self.create_task(self.write_metadata(scrape_item, f"post_{post_id}", post))
        self._post(scrape_item, post)

    def _post(self, scrape_item: ScrapeItem, post: Post) -> None:
        seen: set[str] = set()
        for url in itertools.chain(post.images, post.videos):
            if url not in seen:
                seen.add(url)
                self.create_task(self.direct_file(scrape_item, self.parse_url(url)))
                scrape_item.add_children()

        if not post.content or self.ignore_content:
            return

        for url in self.__parse_content_urls(post):
            self.handle_external_links(scrape_item.create_child(url))
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

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem) -> None:
        async for soup in self.web_pager(scrape_item.url):
            for _, child in self.iter_children(scrape_item, soup, "a.view-post[href]"):
                self.create_task(self.run(child))


def _parse_post(soup: BeautifulSoup) -> Post:
    main = css.select(soup, "main.content")
    body = css.select(main, ".post-body")

    def get(attr: str) -> str:
        return css.select_text(main, attr)

    return Post(
        title=get("h1"),
        model_name=get(".model-name"),
        content=get(".post-date + p"),
        date=extr_text(get(".post-date"), "Added ", " +"),
        images=tuple(css.iselect(body, "img", "src")),
        videos=tuple(css.iselect(body, "source", "src")),
    )
