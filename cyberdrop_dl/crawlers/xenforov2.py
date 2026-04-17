"""Generic crawler for any Xenforo

A Xenforo site has these attributes attached to the main html tag of the site:
id="XF"                                  This identifies the site as a Xenforo site
data-cookie-prefix="ogaddgmetaprof_"     The full cookies name will be `ogaddgmetaprof_user`
data-xf="2.3"                            Version number


Xenforo sites have a REST API but the APi is private only. Admins of the site need to grand access user by user
"""

# ruff : noqa: RUF009
from __future__ import annotations

import asyncio
import base64
import dataclasses
import datetime
import re
from typing import TYPE_CHECKING, ClassVar, final

from bs4 import BeautifulSoup, Tag

from cyberdrop_dl.crawlers.crawler import Crawler
from cyberdrop_dl.exceptions import LoginError, MaxChildrenError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, get_text_between, is_blob_or_svg
from cyberdrop_dl.utils.dates import TimeStamp, to_timestamp

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable, Sequence

    from aiohttp import ClientResponse

    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem

LINK_TRASH_MAPPING = {".th.": ".", ".md.": ".", "ifr": "watch"}
HTTP_REGEX_LINKS = re.compile(
    r"https?://(www\.)?[-a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,12}\b([-a-zA-Z0-9@:%_+.~#?&/=]*)"
)


Selector = css.CssAttributeSelector


@dataclasses.dataclass(frozen=True, slots=True)
class PostSelectors:
    article: str  # the entire html of the post (comments, attachments, user avatar, signature, etc...)
    content: str  # text, links and images (NO attachments)
    id: Selector
    attachments: Selector
    article_trash: Sequence[str] = ("signature", "footer")
    content_trash: Sequence[str] = ("blockquote", "fauxBlockLink")

    # Most sites should only need to overwrite the attributes above
    date: Selector = Selector("time", "datetime")
    embeds: Selector = Selector("iframe", "src")
    images: Selector = Selector("img.bbImage", "src")
    a_tag_w_image: Selector = Selector("a:has(img.bbImage)[href]", "href")
    lazy_load_embeds: Selector = Selector('[class*=iframe][onclick*="loadMedia(this, \'//"]', "onclick")
    links: Selector = Selector("a:not(:has(img))", "href")
    videos: Selector = Selector("video source", "src")


@dataclasses.dataclass(frozen=True, slots=True)
class MessageBoardSelectors:
    posts: PostSelectors
    confirmation_button: Selector
    next_page: Selector
    last_page: Selector
    current_page: Selector
    title: Selector
    title_trash: Sequence[str] = ("span",)


@dataclasses.dataclass(frozen=True, slots=True, order=True)
class ForumPost:
    id: int
    date: datetime.datetime | None
    article: Tag = dataclasses.field(compare=False)
    content: Tag = dataclasses.field(compare=False)

    @staticmethod
    def new(article: Tag, selectors: PostSelectors) -> ForumPost:
        for trash in selectors.article_trash:
            css.decompose(article, trash)
        content = css.select(article, selectors.content)
        for trash in selectors.content_trash:
            css.decompose(article, trash)
        try:
            date = datetime.datetime.fromisoformat(css.select(article, *selectors.date))
        except Exception:
            date = None

        id_str = css.attr(article, selectors.id.attribute)
        post_id = int(id_str.rsplit("-", 1)[-1])
        return ForumPost(post_id, date, article, content)

    @property
    def timestamp(self) -> TimeStamp | None:
        if self.date:
            return to_timestamp(self.date)


@dataclasses.dataclass(frozen=True, slots=True, order=True)
class Thread:
    id: int
    name: str
    page: int
    post_id: int | None
    url: AbsoluteHttpURL


def iter_links(links: Iterable[Tag], attribute: str) -> Iterable[str]:
    for link_tag in links:
        try:
            yield css.attr(link_tag, attribute)
        except Exception:
            continue


def parse_thread(url: AbsoluteHttpURL, thread_name_and_id: str, page_part_name: str, post_part_name: str) -> Thread:
    name_index = url.parts.index(thread_name_and_id)
    name, id_ = parse_thread_name_and_id(thread_name_and_id)
    page, post_id = get_thread_page_and_post(url, name_index, page_part_name, post_part_name)
    canonical_url = get_thread_canonical_url(url, name_index)
    return Thread(id_, name, page, post_id, canonical_url)


def parse_thread_name_and_id(thread_name_and_id: str) -> tuple[str, int]:
    try:
        name, id_str = thread_name_and_id.rsplit(".", 1)
    except ValueError:
        id_str, name = thread_name_and_id.split("-", 1)
    return name, int(id_str)


def get_thread_canonical_url(url: AbsoluteHttpURL, thread_name_index: int) -> AbsoluteHttpURL:
    new_parts = url.parts[1 : thread_name_index + 1]
    new_path = "/".join(new_parts)
    return url.with_path(new_path)


def get_thread_page_and_post(
    url: AbsoluteHttpURL, thread_name_index: int, page_name: str, post_name: str
) -> tuple[int, int | None]:
    extra_parts = url.parts[thread_name_index + 1 :]
    if url.fragment:
        extra_parts = *extra_parts, url.fragment

    def find_number(search_value: str) -> int | None:
        for sec in extra_parts:
            if search_value in sec:
                return int(sec.rsplit(search_value, 1)[-1].replace("-", "").strip())

    post_id = find_number(post_name)
    page_number = find_number(page_name) or 1
    return page_number, post_id


async def check_is_not_last_page(response: ClientResponse, selectors: MessageBoardSelectors) -> bool:
    soup = BeautifulSoup(await response.text(), "html.parser")
    return not is_last_page(soup, selectors)


def is_last_page(soup: BeautifulSoup, selectors: MessageBoardSelectors) -> bool:
    try:
        last_page = css.select(soup, *selectors.last_page)
        current_page = css.select(soup, *selectors.current_page)
    except (AttributeError, IndexError, css.SelectorError):
        return True
    return current_page == last_page


def get_post_title(soup: BeautifulSoup, selectors: MessageBoardSelectors) -> str:
    try:
        title_block = css.select(soup, selectors.title.element)
        for trash in selectors.title_trash:
            css.decompose(title_block, trash)
    except (AttributeError, AssertionError, css.SelectorError) as e:
        raise ScrapeError(429, message="Invalid response from forum. You may have been rate limited") from e

    if title := " ".join(css.text(title_block).split()):
        return title
    raise ScrapeError(422)


def extract_embed_url(embed_str: str) -> str:
    embed_str = embed_str.replace(r"\/\/", "https://www.").replace("\\", "")
    if match := re.search(HTTP_REGEX_LINKS, embed_str):
        return match.group(0).replace("www.", "")
    return embed_str


def clean_link_str(link: str) -> str:
    for old, new in LINK_TRASH_MAPPING.items():
        link = link.replace(old, new)
    return link


def is_confirmation_link(link: AbsoluteHttpURL) -> bool:
    return (
        "masked" in link.parts or "link-confirmation" in link.path or ("redirect" in link.parts and "to" in link.query)
    )


def check_post_id(init_post_id: int | None, current_post_id: int, scrape_single_forum_post: bool) -> tuple[bool, bool]:
    """Checks if the program should scrape the current post.

    Returns (continue_scraping, scrape_this_post)"""
    if init_post_id:
        if init_post_id > current_post_id:
            return (True, False)
        elif init_post_id == current_post_id:
            return (not scrape_single_forum_post, True)
        else:
            return (not scrape_single_forum_post, not scrape_single_forum_post)

    assert not scrape_single_forum_post  # We should have raised an exception earlier
    return True, True


def pre_process_child(link_str: str, embeds: bool = False) -> str | None:
    assert isinstance(link_str, str)
    if embeds:
        link_str = extract_embed_url(link_str)

    if link_str and not is_blob_or_svg(link_str):
        return link_str


Selector = css.CssAttributeSelector


DEFAULT_XF_POST_SELECTORS = PostSelectors(
    article="article.message[id*=post]",
    content=".message-userContent",
    article_trash=(".message-signature", ".message-footer"),
    content_trash=("blockquote", "fauxBlockLink"),
    id=Selector("article.message[id*=post]", "id"),
    attachments=Selector(".message-attachments a[href]", "href"),
)


DEFAULT_XF_SELECTORS = MessageBoardSelectors(
    posts=DEFAULT_XF_POST_SELECTORS,
    confirmation_button=Selector("a[class*=button--cta][href]", "href"),
    next_page=Selector("a[class*=pageNav-jump--next][href]", "href"),
    title_trash=("span",),
    title=Selector("h1[class*=p-title-value]"),
    last_page=Selector("li.pageNav-page a:last-of-type", "href"),
    current_page=Selector("li.pageNav-page.pageNav-page--current a", "href"),
)


def _escape(strings: Iterable[str]) -> str:
    return r"\|".join(strings)


class XenforoCrawler(Crawler, is_abc=True):
    ATTACHMENT_URL_PARTS: ClassVar[Sequence[str]] = "attachments", "data", "uploads"
    THREAD_PART_NAMES: ClassVar[Sequence[str]] = "thread", "topic", "tema", "threads", "topics", "temas"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Attachments": f"/({_escape(ATTACHMENT_URL_PARTS)})/...",
        "Threads": (
            f"/({_escape(THREAD_PART_NAMES)})/<thread_name_and_id>",
            "/posts/<post_id>",
            "/goto/<post_id>",
        ),
        "**NOTE**": "base crawler: Xenforo",
    }
    SUPPORTS_THREAD_RECURSION: ClassVar[bool] = True
    SELECTORS: ClassVar[MessageBoardSelectors] = DEFAULT_XF_SELECTORS
    POST_URL_PART_NAME: ClassVar[str] = "post"
    PAGE_URL_PART_NAME: ClassVar[str] = "page"
    IGNORE_EMBEDED_IMAGES_SRC: ClassVar[bool] = True
    LOGIN_USER_COOKIE_NAME: ClassVar[str] = "xf_user"
    # Attachments hosts should technically be defined on each specific Crawler, but they do no harm here
    ATTACHMENT_HOSTS = "smgmedia", "attachments.f95zone"

    login_required: ClassVar[bool | None] = None

    def __post_init__(self) -> None:
        self.scraped_threads = set()

    async def __async_post_init__(self) -> None:
        await self.login()

    @final
    async def login(self) -> None:
        if self.login_required is None:
            return

        if not self._logged_in:
            login_url = self.PRIMARY_URL / "login"
            await self._login(login_url)

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
            case [thread_part, thread_name_and_id, *_] if thread_part in self.THREAD_PART_NAMES:
                self.check_thread_recursion(scrape_item)
                thread = self.parse_thread(scrape_item.url, thread_name_and_id)
                return await self.thread(scrape_item, thread)
            case ["masked" | "link-confirmation" | "redirect", *_]:
                return await self.follow_confirmation_link(scrape_item)
            case ["goto" | "posts", _, *_]:
                self.check_thread_recursion(scrape_item)
                return await self.follow_redirect(scrape_item)
            case _:
                raise ValueError

    def is_attachment(self, link: AbsoluteHttpURL | str) -> bool:
        if not link:
            return False
        if isinstance(link, str):
            link = self.parse_url(link)
        by_parts = len(link.parts) > 2 and any(p in link.parts for p in self.ATTACHMENT_URL_PARTS)
        by_host = any(host in link.host for host in self.ATTACHMENT_HOSTS)
        return by_parts or by_host

    @final
    async def follow_confirmation_link(self, scrape_item: ScrapeItem) -> None:
        url = await self.resolve_confirmation_link(scrape_item.url)
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

        self.limit_nexted_thread_folders(scrape_item)

    @final
    def limit_nexted_thread_folders(self, scrape_item: ScrapeItem) -> None:
        if self.max_thread_folder_depth is None:
            return
        n_parents = len(scrape_item.parent_threads)
        if n_parents > self.max_thread_folder_depth:
            scrape_item.parent_title = scrape_item.parent_title.rsplit("/", 1)[0]
            if not self.separate_posts:
                return
            scrape_item.parent_title = scrape_item.parent_title.rsplit("/", 1)[0]

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
        if link == self.PRIMARY_URL:
            return
        if self.is_attachment(link):
            return await self.handle_internal_link(scrape_item, link)
        if self.PRIMARY_URL.host == link.host:
            self.create_task(self.run(scrape_item.create_child(link)))
            return
        new_scrape_item = scrape_item.create_child(link)
        self.handle_external_links(new_scrape_item)
        scrape_item.add_children()

    # TODO: Move this to the base crawler
    # TODO: Define an unified workflow for crawlers to perform and check login
    @final
    @error_handling_wrapper
    async def _login(self, login_url: AbsoluteHttpURL) -> None:
        session_cookie = self.get_cookie_value(self.LOGIN_USER_COOKIE_NAME)
        msg = f"No cookies found for {self.FOLDER_DOMAIN}"
        if not session_cookie and self.login_required:
            raise LoginError(message=msg)

        _, self._logged_in = await self.check_login_with_request(login_url)
        if self._logged_in:
            return
        if session_cookie:
            msg = f"Cookies for {self.FOLDER_DOMAIN} are not valid."
        if self.login_required:
            raise LoginError(message=msg)

        msg += " Scraping without an account"
        self.log.warning(msg)

    async def check_login_with_request(self, login_url: AbsoluteHttpURL) -> tuple[str, bool]:
        text = await self.request_text(login_url, cache_disabled=True)
        logged_in = '<span class="p-navgroup-user-linkText">' in text or "You are already logged in." in text
        return text, logged_in

    @error_handling_wrapper
    async def thread(self, scrape_item: ScrapeItem, /, thread: Thread) -> None:
        scrape_item.setup_as_forum("")
        if thread.url in self.scraped_threads:
            return

        scrape_item.parent_threads.add(thread.url)
        self.scraped_threads.add(thread.url)
        await self._thread(scrape_item, thread)

    async def _thread(self, scrape_item: ScrapeItem, thread: Thread) -> None:
        title: str = ""
        async for soup in self.thread_pager(scrape_item):
            if not title:
                try:
                    title = self.create_title(get_post_title(soup, self.SELECTORS), thread_id=thread.id)
                except ScrapeError as e:
                    self.log.debug("Got an unprocessable soup", exc_info=e)
                    raise
                scrape_item.add_to_parent_title(title)

            continue_scraping, _ = self._thread_page(scrape_item, thread, soup)
            if not continue_scraping:
                break

    def _thread_page(self, scrape_item: ScrapeItem, thread: Thread, soup: BeautifulSoup) -> bool:
        continue_scraping = False
        post_url = thread.url
        for article in soup.select(self.SELECTORS.posts.article):
            current_post = ForumPost.new(article, self.SELECTORS.posts)
            continue_scraping, scrape_this_post = check_post_id(
                thread.post_id, current_post.id, self.scrape_single_forum_post
            )
            if scrape_this_post:
                post_url = self.make_post_url(thread, current_post.id)
                new_scrape_item = scrape_item.create_new(
                    thread.url,
                    possible_datetime=current_post.timestamp,
                    add_parent=post_url,
                )
                self.create_task(self.post(new_scrape_item, current_post))
                try:
                    scrape_item.add_children()
                except MaxChildrenError:
                    break

            if not continue_scraping:
                break
        return continue_scraping

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post: ForumPost) -> None:
        scrape_item.setup_as_post("")
        post_title = self.create_separate_post_title(None, str(post.id), post.date)
        scrape_item.add_to_parent_title(post_title)
        seen, duplicates, tasks = set(), set(), []
        stats: dict[str, int] = {}
        max_children_error: MaxChildrenError | None = None
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
                    tasks.append(self.process_child(scrape_item, link, embeds="embeds" in scraper_name))
                    scrape_item.add_children()
        except MaxChildrenError as e:
            max_children_error = e

        if seen:
            self.log.info(f"post #{post.id} {stats = }")
        if duplicates:
            msg = f"Found duplicate links in post {scrape_item.parent}. Selectors are too generic: {duplicates}"
            self.log.warning(msg)

        await asyncio.gather(*tasks)
        if max_children_error is not None:
            raise max_children_error

    def _external_links(self, post: ForumPost) -> Iterable[str]:
        selector = self.SELECTORS.posts.links
        links = css.iselect(post.content, selector.element)
        valid_links = (link for link in links if not self.is_username_or_attachment(link))
        return iter_links(valid_links, selector.attribute)

    def _images(self, post: ForumPost) -> Iterable[str]:
        if self.IGNORE_EMBEDED_IMAGES_SRC:
            selector = self.SELECTORS.posts.a_tag_w_image
        else:
            selector = self.SELECTORS.posts.images
        images = css.iselect(post.content, selector.element)
        return iter_links(images, selector.attribute)

    def _videos(self, post: ForumPost) -> Iterable[str]:
        selector = self.SELECTORS.posts.videos
        videos = css.iselect(post.content, selector.element)
        return iter_links(videos, selector.attribute)

    def _attachments(self, post: ForumPost) -> Iterable[str]:
        selector = self.SELECTORS.posts.attachments
        attachments = css.iselect(post.article, selector.element)
        return iter_links(attachments, selector.attribute)

    def _embeds(self, post: ForumPost) -> Iterable[str]:
        selector = self.SELECTORS.posts.embeds
        embeds = css.iselect(post.content, selector.element)
        return iter_links(embeds, selector.attribute)

    def _lazy_load_embeds(self, post: ForumPost) -> Iterable[str]:
        selector = self.SELECTORS.posts.lazy_load_embeds
        for lazy_media in css.iselect(post.content, selector.element):
            yield get_text_between(css.attr(lazy_media, selector.attribute), "loadMedia(this, '", "')")

    async def thread_pager(self, scrape_item: ScrapeItem) -> AsyncGenerator[BeautifulSoup]:
        async for soup in self.web_pager(scrape_item.url, self.get_next_page):
            yield soup

    def get_next_page(self, soup: BeautifulSoup) -> str | None:
        try:
            return css.select(soup, *self.SELECTORS.next_page)
        except css.SelectorError:
            return

    @final
    @error_handling_wrapper
    async def process_child(self, scrape_item: ScrapeItem, link_str: str, *, embeds: bool = False) -> None:
        link_str_ = pre_process_child(link_str, embeds)
        if not link_str_:
            return
        link = await self.get_absolute_link(link_str_)
        if not link:
            return
        await self.handle_link(scrape_item, link)

    async def get_absolute_link(self, link: str | AbsoluteHttpURL) -> AbsoluteHttpURL | None:
        if isinstance(link, str):
            absolute_link = self.parse_url(clean_link_str(link))
        else:
            absolute_link = link
        if is_confirmation_link(absolute_link):
            return await self.resolve_confirmation_link(absolute_link)
        return absolute_link

    @error_handling_wrapper
    async def resolve_confirmation_link(self, link: AbsoluteHttpURL) -> AbsoluteHttpURL | None:
        if url := link.query.get("url") or link.query.get("to"):
            padding = -len(url) % 4
            url = base64.urlsafe_b64decode(url + "=" * padding).decode("utf-8")
            if url.startswith("https://"):
                return self.parse_url(url)

        soup = await self.request_soup(link)
        selector = self.SELECTORS.confirmation_button
        confirm_button = soup.select_one(selector.element)
        if not confirm_button:
            return

        link_str: str = css.attr(confirm_button, selector.attribute)
        link_str = link_str.split('" class="link link--internal', 1)[0]
        new_link = self.parse_url(link_str)
        return await self.get_absolute_link(new_link)

    async def handle_internal_link(self, scrape_item: ScrapeItem, link: AbsoluteHttpURL | None = None) -> None:
        link = link or scrape_item.url
        slug = link.name or link.parent.name
        if slug.isdigit():
            return await self.follow_redirect(scrape_item.create_new(link))

        link = link or scrape_item.url
        filename, ext = self.get_filename_and_ext(link.name)
        new_scrape_item = scrape_item.copy()
        new_scrape_item.add_to_parent_title("Attachments")
        new_scrape_item.part_of_album = True
        await self.handle_file(link, new_scrape_item, filename, ext)

    def is_username_or_attachment(self, link_obj: Tag) -> bool:
        if link_obj.select_one(".username"):
            return True
        try:
            if link_str := css.attr(link_obj, self.SELECTORS.posts.links.element):
                return self.is_attachment(link_str)
        except Exception:
            pass
        return False

    def get_filename_and_ext(self, filename: str) -> tuple[str, str]:
        # The `forum` keyword is misleading now. It only works for Xenforo sites, not every forum
        # TODO: Change `forum` parameter to `xenforo`
        return super().get_filename_and_ext(filename, forum=True)
