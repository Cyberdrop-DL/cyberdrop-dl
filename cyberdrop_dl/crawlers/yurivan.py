from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from pydantic import dataclasses

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import deserialize, error_handling_wrapper, next_js

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


class YuriVanCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Chapter": "/story/<story_id>/read?chapter<chapter_id>",
        "Story": "/story/<story_id>",
    }
    DOMAIN: ClassVar[str] = "yurivan"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.yurivan.com")

    async def __async_post_init__(self) -> None:
        self.update_cookies({"age_verified": "remember", "yh_sfs": "same-origin"})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["story", story_id]:
                return await self.story(scrape_item, story_id)
            case ["story", story_id, "read"] if chapter := scrape_item.url.query.get("chapter"):
                return await self.chapter(scrape_item, story_id, int(chapter))
            case _:
                raise ValueError

    @error_handling_wrapper
    async def story(self, scrape_item: ScrapeItem, story_id: str) -> None:
        scrape_item.setup_as_album("")
        soup = await self.request_soup(scrape_item.url)

        selector = f"a[href*='/story/{story_id}/read']"
        for _, new_item in self.iter_children(scrape_item, soup, selector):
            self.create_task(self.run(new_item))
            scrape_item.add_children()

    @error_handling_wrapper
    async def chapter(self, scrape_item: ScrapeItem, story_id: str, chapter_id: int) -> None:
        chapter_idx = chapter_id - 1
        soup = await self.request_soup(scrape_item.url)
        story = _extract_story(soup, chapter_idx)
        title = self.create_title(story.storyTitle, story_id)
        scrape_item.setup_as_album(title, album_id=story_id)

        chapter = story.chapters[chapter_idx]
        scrape_item.add_to_parent_title(self.create_title(chapter.title))
        for page in chapter.pages:
            await self.direct_file(scrape_item, page.url)
            scrape_item.add_children()


@dataclasses.dataclass(slots=True)
class Story:
    storyId: str  # noqa: N815
    storyTitle: str  # noqa: N815
    chapters: tuple[Chapter, ...]


@dataclasses.dataclass(slots=True)
class Chapter:
    chapter_index: int
    title: str
    cover_url: str
    pages: tuple[Page, ...] = ()


@dataclasses.dataclass(slots=True)
class Page:
    url: AbsoluteHttpURL
    bytes: int


def _extract_story(soup: BeautifulSoup, chapter_index: int) -> Story:
    next_data = next_js.extract(soup)
    for s in next_js.ifind(next_data, "storyId", "storyTitle", "chapters"):
        story = deserialize(Story, s)
        if len(story.chapters) > chapter_index and story.chapters[chapter_index].pages:
            return story
    raise ScrapeError(422, "Unable to extract story info")
