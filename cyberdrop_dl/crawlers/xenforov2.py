"""Generic crawler for any Xenforo

A Xenforo site has these attributes attached to the main html tag of the site:
id="XF"                                  This identifies the site as a Xenforo site
data-cookie-prefix="ogaddgmetaprof_"     The full cookies name will be `ogaddgmetaprof_user`
data-xf="2.3"                            Version number


Xenforo sites have a REST API but the APi is private only. Admins of the site need to grand access user by user
"""

from __future__ import annotations

import base64
import dataclasses
import re
from typing import TYPE_CHECKING, Any, ClassVar, Self, final

from cyberdrop_dl.crawlers.crawler import Crawler
from cyberdrop_dl.exceptions import MaxChildrenError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, dates, error_handling_wrapper, get_text_between, is_blob_or_svg, parse_url
from cyberdrop_dl.utils.dates import TimeStamp, to_timestamp

if TYPE_CHECKING:
    import datetime
    from collections.abc import Iterable, Sequence

    from bs4 import BeautifulSoup, Tag

    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem


_HTTP_REGEX_LINKS = re.compile(
    r"https?://(www\.)?[-a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,12}\b([-a-zA-Z0-9@:%_+.~#?&/=]*)"
)


_Selector = css.CssAttributeSelector


class PostSelectors:
    ARTICLE = "article.message[id*=post]"
    CONTENT = ".message-userContent"
    ARTICLE_TRASH = (".message-signature", ".message-footer")
    CONTENT_TRASH = ("blockquote", "fauxBlockLink")
    ID = _Selector("article.message[id*=post]", "id")
    ATTACHMENTS = _Selector(".message-attachments a[href]", "href")

    DATE = _Selector("time", "datetime")
    EMBEDS = _Selector("iframe", "src")
    IMAGES = _Selector("img.bbImage", "src")
    HREF_IMAGES = _Selector("a:has(img.bbImage)[href]", "href")
    LAZY_LOAD_EMBEDS = _Selector('[class*=iframe][onclick*="loadMedia(this, \'//"]', "onclick")
    LINKS = _Selector("a:not(:has(img))", "href")
    VIDEOS = _Selector("video source", "src")


class Selectors:
    CONFIRM_BTN = _Selector("a[class*=button--cta][href]", "href")
    NEXT_PAGE = "a[class*=pageNav-jump--next][href]"


@dataclasses.dataclass(slots=True, order=True)
class Post:
    id: int
    date: datetime.datetime | None
    article: Tag = dataclasses.field(compare=False)
    content: Tag = dataclasses.field(compare=False)

    @staticmethod
    def parse(article: Tag) -> Post:
        for trash in PostSelectors.ARTICLE_TRASH:
            css.decompose(article, trash)
        content = css.select(article, PostSelectors.CONTENT)
        for trash in PostSelectors.CONTENT_TRASH:
            css.decompose(article, trash)
        try:
            date = dates.parse_iso(css.select(article, *PostSelectors.DATE))
        except Exception:
            date = None

        id_str = css.attr(article, PostSelectors.ID.attribute)
        post_id = int(id_str.rpartition("-")[-1])
        return Post(post_id, date, article, content)

    @property
    def timestamp(self) -> TimeStamp | None:
        if self.date:
            return to_timestamp(self.date)


@dataclasses.dataclass(slots=True, order=True)
class Thread:
    id: int
    name: str
    url: AbsoluteHttpURL
    created_at: datetime.datetime

    @classmethod
    def parse(cls, soup: BeautifulSoup) -> Self:
        main: dict[str, Any] = css.json_ld(soup)["mainEntity"]
        url = parse_url(main["url"])

        return cls(
            id=int(url.name.rpartition(".")[-1]),
            name=main["headline"],
            created_at=dates.parse_iso(main["datePublished"]),
            url=url,
        )


def _extract_embed_url(embed_str: str) -> str:
    embed_str = embed_str.replace(r"\/\/", "https://www.").replace("\\", "")
    if match := re.search(_HTTP_REGEX_LINKS, embed_str):
        return match.group(0).replace("www.", "")
    return embed_str


def is_confirmation_link(link: AbsoluteHttpURL) -> bool:
    return (
        "masked" in link.parts or "link-confirmation" in link.path or ("redirect" in link.parts and "to" in link.query)
    )


_Selector = css.CssAttributeSelector


class XenforoCrawler(Crawler, is_abc=True):
    THREAD_PART_NAMES: ClassVar[Sequence[str]] = "thread", "topic", "tema", "threads", "topics", "temas"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Attachments": "/attachments/...",
        "Threads": (
            "/thread/<thread_name_and_id>/posts/<post_id>",
            "/goto/<post_id>",
        ),
        "**NOTE**": "base crawler: Xenforo",
    }
    SUPPORTS_THREAD_RECURSION: ClassVar[bool] = True

    POST_URL_PART_NAME: ClassVar[str] = "post"
    PAGE_URL_PART_NAME: ClassVar[str] = "page"
    IGNORE_EMBEDED_IMAGES_SRC: ClassVar[bool] = True
    LOGIN_USER_COOKIE_NAME: ClassVar[str] = "xf_user"
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selectors.NEXT_PAGE

    login_required: ClassVar[bool | None] = None

    def __post_init__(self) -> None:
        self.scraped_threads = set()

    @final
    @property
    def max_thread_depth(self) -> int:
        return self.manager.config.settings.download_options.maximum_thread_depth

    @final
    @property
    def max_thread_folder_depth(self):
        return self.manager.config.settings.download_options.maximum_thread_folder_depth

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if not self._logged_in and self.login_required is True:
            return

        match scrape_item.url.parts[1:]:
            case ["attachments" | "data" | "uploads", _, *_]:
                return await self.handle_internal_link(scrape_item)
            case ["thread" | "topic" | "tema" | "threads" | "topics" | "temas", _, *_]:
                self.check_thread_recursion(scrape_item)
                return await self.thread(scrape_item)
            case ["masked" | "link-confirmation" | "redirect", *_]:
                return await self.follow_confirmation_link(scrape_item)
            case ["goto" | "posts", _, *_]:
                self.check_thread_recursion(scrape_item)
                return await self.follow_redirect(scrape_item)
            case _:
                raise ValueError

    @final
    async def follow_confirmation_link(self, scrape_item: ScrapeItem) -> None:
        url = await self._resolve_confirmation_link(scrape_item.url)
        if url:  # If there was an error, this will be None
            scrape_item.url = url
            # This could end up back in here if the URL goes to another thread
            return self.handle_external_links(scrape_item)

    @final
    def check_thread_recursion(self, scrape_item: ScrapeItem) -> None:
        if self.stop_thread_recursion(scrape_item):
            parents = f"{len(scrape_item.parent_threads)} parent thread(s)"
            msg = (
                f"Skipping nested thread URL with {parents}:"
                f"URL: {scrape_item.url}\n"
                f"Parent:  {scrape_item.parent}\n"
                f"Origin:  {scrape_item.origin}\n"
            )
            raise MaxChildrenError(msg)

    @final
    def stop_thread_recursion(self, scrape_item: ScrapeItem) -> bool:
        if n_parents := len(scrape_item.parent_threads):
            if n_parents > self.max_thread_depth:
                return True

            return self.SUPPORTS_THREAD_RECURSION and bool(self.max_thread_depth)

        return False

    @final
    @error_handling_wrapper
    async def handle_link(self, scrape_item: ScrapeItem, link: AbsoluteHttpURL) -> None:
        new_scrape_item = scrape_item.create_child(link)
        self.handle_external_links(new_scrape_item)
        scrape_item.add_children()

    @error_handling_wrapper
    async def thread(self, scrape_item: ScrapeItem, /) -> None:
        thread: Thread | None = None
        async for soup in self.web_pager(scrape_item.url):
            if thread is None:
                thread = Thread.parse(soup)
                scrape_item.setup_as_forum(self.create_title(thread.name))

            self._thread_page(scrape_item, thread, soup)

    def _thread_page(self, scrape_item: ScrapeItem, thread: Thread, soup: BeautifulSoup) -> None:
        for article in css.iselect(soup, PostSelectors.ARTICLE):
            post = Post.parse(article)
            post_url = thread.url / f"post-{post.id}"
            new_scrape_item = scrape_item.create_new(thread.url, add_parent=post_url)
            new_scrape_item.uploaded_at = post.timestamp
            self.create_task(self._post(new_scrape_item, post))
            scrape_item.add_children()

    @error_handling_wrapper
    async def _post(self, scrape_item: ScrapeItem, post: Post) -> None:
        scrape_item.setup_as_post("")
        post_title = self.create_separate_post_title(None, str(post.id), post.date)
        scrape_item.add_to_parent_title(post_title)
        seen, duplicates = set(), set()
        stats: dict[str, int] = {}

        async with self.new_task_group(scrape_item) as tg:
            try:
                for scraper in (
                    self._attachments,
                    self._images,
                    self._videos,
                    self._external_links,
                    self._embeds,
                    self._lazy_load_embeds,
                ):
                    for link in scraper(post):
                        duplicates.add(link) if link in seen else seen.add(link)
                        scraper_name = scraper.__name__.removeprefix("_")
                        stats[scraper_name] = stats.get(scraper_name, 0) + 1
                        tg.create_task(
                            self.process_child(
                                scrape_item,
                                link,
                                embeds="embeds" in scraper_name,
                            ),
                        )
                        scrape_item.add_children()

            finally:
                if stats:
                    self.log.info(f"post #{post.id} {stats = }")
                if duplicates:
                    msg = f"Found duplicate links in post {scrape_item.parent}. Selectors are too generic: {duplicates}"
                    self.log.warning(msg)

    def _external_links(self, post: Post) -> Iterable[str]:
        selector = PostSelectors.LINKS
        links = css.iselect(post.content, selector.element)
        return self._iter_links(links, selector.attribute)

    def _images(self, post: Post) -> Iterable[str]:
        if self.IGNORE_EMBEDED_IMAGES_SRC:
            selector = PostSelectors.HREF_IMAGES
        else:
            selector = PostSelectors.IMAGES
        images = css.iselect(post.content, selector.element)
        return self._iter_links(images, selector.attribute)

    def _videos(self, post: Post) -> Iterable[str]:
        selector = PostSelectors.VIDEOS
        videos = css.iselect(post.content, selector.element)
        return self._iter_links(videos, selector.attribute)

    def _attachments(self, post: Post) -> Iterable[str]:
        selector = PostSelectors.ATTACHMENTS
        attachments = css.iselect(post.article, selector.element)
        return self._iter_links(attachments, selector.attribute)

    def _embeds(self, post: Post) -> Iterable[str]:
        selector = PostSelectors.EMBEDS
        embeds = css.iselect(post.content, selector.element)
        return self._iter_links(embeds, selector.attribute)

    def _lazy_load_embeds(self, post: Post) -> Iterable[str]:
        selector = PostSelectors.LAZY_LOAD_EMBEDS
        for lazy_media in css.iselect(post.content, *selector):
            yield get_text_between(lazy_media, "loadMedia(this, '", "')")

    def _iter_links(self, links: Iterable[Tag], attribute: str) -> Iterable[str]:
        for link_tag in links:
            try:
                yield css.attr(link_tag, attribute)
            except css.SelectorError:
                self.log.debug("Unable to parse some links in post", exc_info=True)
                continue

    @final
    @error_handling_wrapper
    async def process_child(self, scrape_item: ScrapeItem, link_str: str, *, embeds: bool = False) -> None:
        assert isinstance(link_str, str)
        if embeds:
            link_str = _extract_embed_url(link_str)

        if is_blob_or_svg(link_str):
            return

        if not link_str:
            return
        link = await self._resolve_url(link_str)
        if not link:
            return
        await self.handle_link(scrape_item, link)

    async def _resolve_url(self, link: str | AbsoluteHttpURL) -> AbsoluteHttpURL | None:
        if isinstance(link, str):
            absolute_link = self.parse_url(link)
        else:
            absolute_link = link

        if is_confirmation_link(absolute_link):
            return await self._resolve_confirmation_link(absolute_link)

        return absolute_link

    @error_handling_wrapper
    async def _resolve_confirmation_link(self, link: AbsoluteHttpURL) -> AbsoluteHttpURL | None:
        if url := link.query.get("url") or link.query.get("to"):
            padding = -len(url) % 4
            url = base64.urlsafe_b64decode(url + "=" * padding).decode("utf-8")
            if url.startswith("https://"):
                return self.parse_url(url)

        soup = await self.request_soup(link)
        selector = Selectors.CONFIRM_BTN
        confirm_button = soup.select_one(selector.element)
        if not confirm_button:
            return

        link_str: str = css.attr(confirm_button, selector.attribute)
        link_str = link_str.split('" class="link link--internal', 1)[0]
        new_link = self.parse_url(link_str)
        return await self._resolve_url(new_link)

    async def handle_internal_link(self, scrape_item: ScrapeItem, link: AbsoluteHttpURL | None = None) -> None:
        link = link or scrape_item.url
        slug = link.name or link.parent.name
        if slug.isdigit():
            return await self.follow_redirect(scrape_item.create_new(link))

        link = link or scrape_item.url
        new_scrape_item = scrape_item.create_child(link)
        await self._attachment(new_scrape_item)

    async def _attachment(self, scrape_item: ScrapeItem) -> None:
        link = scrape_item.url
        filename, ext = self.get_filename_and_ext(link.name, forum=True)
        scrape_item.add_to_parent_title("Attachments")
        scrape_item.part_of_album = True
        await self.handle_file(link, scrape_item, filename, ext)
