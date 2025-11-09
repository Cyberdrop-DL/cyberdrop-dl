from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


PRIMARY_URL = AbsoluteHttpURL("https://fsiblog5.com")


class PostType(StrEnum):
    VIDEO = "3356d45d"
    IMAGES = "1beff4ae"
    STORY = "4683db71"


class FSIBlogCrawler(Crawler):
    SUPPORTED_DOMAINS = "fsiblog5.com", "fsiblog5.club"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Posts": "/<category>/<title>", "Search": "?s=<query>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "fsiblog.com"
    FOLDER_DOMAIN: ClassVar[str] = "FSIBlog"
    OLD_DOMAINS = (
        "fsiblog.com",
        "fsiblog1.com",
        "fsiblog2.com",
        "fsiblog3.com",
        "fsiblog4.com",
        "fsiblog.club",
        "fsiblog1.club",
        "fsiblog2.club",
        "fsiblog3.club",
        "fsiblog4.club",
    )

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if query := scrape_item.url.query.get("s"):
            return await self.search(scrape_item, query)
        if len(scrape_item.url.parts) == 3:
            return await self.filter(scrape_item)
        raise ValueError

    @error_handling_wrapper
    async def filter(self, scrape_item: ScrapeItem, post_type: str | None = None) -> None:
        if not post_type:
            soup = await self.request_soup(scrape_item.url)
            post_type = soup.select_one("section.elementor-section.elementor-inner-section").get("data-id")
        if post_type == PostType.VIDEO:
            return await self.video(scrape_item, soup)
        elif post_type == PostType.IMAGES:
            return await self.images(scrape_item, soup)
        elif post_type == PostType.STORY:
            raise ValueError
            return await self.story(scrape_item, soup)
        else:
            raise ValueError

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(query)
        scrape_item.setup_as_album(title)
        async for soup in self.web_pager(scrape_item.url, next_page_selector="a.next"):
            for post in soup.select("div.elementor-posts-container > article > div > a"):
                post_type = PostType(css.get_attr(post.parent, "data-id"))
                post_link = self.parse_url(css.get_attr(post, "href"))
                new_scrape_item = scrape_item.create_child(post_link)
                self.create_task(self.filter(new_scrape_item, post_type))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, soup: BeautifulSoup | None = None) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return
        soup = soup or await self.request_soup(scrape_item.url)

        metadata = self.read_metadata(soup)
        published_date = metadata[0]["datePublished"]
        scrape_item.possible_datetime = self.parse_iso_date(published_date)

        video_url = self.parse_url(open_graph.get("video", soup))
        title = soup.select_one("h1.elementor-heading-title").text.strip()
        filename, ext = self.get_filename_and_ext(video_url.name)
        custom_filename = self.create_custom_filename(title, ext)
        return await self.handle_file(video_url, scrape_item, filename, ext, custom_filename=custom_filename)

    @error_handling_wrapper
    async def images(self, scrape_item: ScrapeItem, soup: BeautifulSoup | None = None) -> None:
        soup = soup or await self.request_soup(scrape_item.url)
        title = self.create_title(soup.select_one("h1.elementor-heading-title").text.strip())
        scrape_item.setup_as_album(title)

        metadata = self.read_metadata(soup)
        published_date = metadata[0]["datePublished"]
        scrape_item.possible_datetime = self.parse_iso_date(published_date)

        image_list = soup.select("a.elementor-gallery-item")
        for image in image_list:
            image_url = self.parse_url(image.get("href"))
            filename, ext = self.get_filename_and_ext(image_url.name)
            await self.handle_file(image_url, scrape_item, filename, ext)

    @error_handling_wrapper
    async def story(self, scrape_item: ScrapeItem, soup: BeautifulSoup | None = None) -> None:
        raise NotImplementedError

    @staticmethod
    def read_metadata(soup: BeautifulSoup) -> dict[str, str]:
        return css.get_json_ld(soup)["@graph"]
