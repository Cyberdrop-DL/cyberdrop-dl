"""Generic crawler for any Xenforo

A Xenforo site has these attributes attached to the main html tag of the site:
id="XF"                                  This identifies the site as a Xenforo site
data-cookie-prefix="ogaddgmetaprof_"     The full cookies name will be `ogaddgmetaprof_user`
data-xf="2.3"                            Version number


Xenforo sites have a REST API but the APi is private only. Admins of the site need to grand access user by user
"""

# ruff : noqa: RUF009
from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import itertools
import json
import re
from typing import TYPE_CHECKING, Any, ClassVar, final

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import LoginError, MaxChildrenError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import b64_pad, css, extr_text, is_blob_or_svg
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import URLDeduper

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Sequence

    from bs4 import BeautifulSoup, Tag

    from cyberdrop_dl.url_objects import ScrapeItem

LINK_TRASH_MAPPING = {".th.": ".", ".md.": ".", "/ifr/": "/watch/"}
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
    date: dt.datetime | None
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
            date = dt.datetime.fromisoformat(css.select(article, *selectors.date))
        except Exception:  # noqa: BLE001
            date = None

        id_str = css.attr(article, selectors.id.attribute)
        post_id = int(id_str.rsplit("-", 1)[-1])
        return ForumPost(post_id, date, article, content)

    @property
    def timestamp(self) -> float | None:
        if self.date:
            return self.date.timestamp()


@dataclasses.dataclass(frozen=True, slots=True, order=True)
class Thread:
    id: int
    name: str
    page: int
    post_id: int | None
    url: AbsoluteHttpURL


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


class XenforoCrawler(Crawler, is_abc=True):
    ATTACHMENT_URL_PARTS: ClassVar[tuple[str, ...]] = "attachments", "data", "uploads"
    ATTACHMENT_HOSTS: ClassVar[Sequence[str]] = "smgmedia", "attachments.f95zone"
    THREAD_PART_NAMES: ClassVar[Sequence[str]] = "thread", "topic", "tema", "threads", "topics", "temas", "themen"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Attachments": f"/{'|'.join(ATTACHMENT_URL_PARTS)}/...",
        "Threads": (
            f"/{'|'.join(THREAD_PART_NAMES)}/<thread_name_and_id>",
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
    _FORUM: ClassVar[bool] = True

    # True: Login is mandatory. If login fails, the crawler will be disabled
    # False: Login is optional, but CDL will try to log in anyway. ex: Forums where only some threads require auth
    # None: Completely skip login check and request. Always try to scrape as is the user is logged in
    # TODO: move login logic to the base crawler
    login_required: ClassVar[bool | None] = True

    def __init_subclass__(cls, *, is_abc: bool = False, **kwargs: Any) -> None:
        super().__init_subclass__(is_abc=is_abc, **kwargs)
        if is_abc:
            return
        REQUIRED_FIELDS = "SELECTORS", "POST_URL_PART_NAME", "PAGE_URL_PART_NAME"
        for field_name in REQUIRED_FIELDS:
            assert getattr(cls, field_name, None), f"Subclass {cls.__name__} must override: {field_name}"

    def __post_init__(self) -> None:
        self.scraped_threads: URLDeduper = URLDeduper()

    async def __async_post_init__(self) -> None:
        if self.login_required is None:
            return

        if not self._logged_in:
            login_url = self.PRIMARY_URL / "login"
            await self.login(login_url)

    @final
    @property
    def max_thread_depth(self) -> int:
        return self.config.max_thread_depth

    @final
    @property
    def max_thread_folder_depth(self) -> int | None:
        return self.config.max_thread_folder_depth

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if not self._logged_in and self.login_required is True:
            return
        scrape_item.url = self.parse_url(str(scrape_item.url))
        if self.is_attachment(scrape_item.url):
            await self.handle_internal_link(scrape_item)
        elif is_confirmation_link(scrape_item.url):
            await self._follow_confirmation_link(scrape_item)
        else:
            await self._fetch_thread(scrape_item)

    async def _fetch_thread(self, scrape_item: ScrapeItem) -> None:
        thread_part_index = len(self.PRIMARY_URL.parts)
        # https://github.com/Cyberdrop-DL/cyberdrop-dl/issues/1165#issuecomment-3086739753
        if self.PRIMARY_URL.parts[-1] == "":
            thread_part_index -= 1
        match scrape_item.url.parts[thread_part_index:]:
            case [thread_part, thread_name_and_id, *_] if thread_part in self.THREAD_PART_NAMES:
                self._check_thread_recursion(scrape_item)
                thread = self.parse_thread(scrape_item.url, thread_name_and_id)
                return await self.thread(scrape_item, thread)
            case ["goto" | "posts", _, *_]:
                self._check_thread_recursion(scrape_item)
                return await self.follow_redirect(scrape_item)
            case ["members", *_]:
                return None
            case [slug] if slug.startswith("#"):
                return None
            case _:
                raise ValueError

    @classmethod
    def is_attachment(cls, link: AbsoluteHttpURL | str) -> bool:
        if not link:
            return False
        if isinstance(link, str):
            link = cls.parse_url(link)
        by_parts = len(link.parts) > 2 and any(p in link.parts for p in cls.ATTACHMENT_URL_PARTS)
        by_host = any(host in link.host for host in cls.ATTACHMENT_HOSTS)
        return by_parts or by_host

    @final
    async def _follow_confirmation_link(self, scrape_item: ScrapeItem) -> None:
        url = await self.resolve_confirmation_link(scrape_item.url)
        if url:  # If there was an error, this will be None
            scrape_item.url = url
            # This could end up back in here if the URL goes to another thread
            return self.handle_external_links(scrape_item)

    @final
    def _check_thread_recursion(self, scrape_item: ScrapeItem) -> None:
        if self.stop_thread_recursion(scrape_item):
            threads = f"{len(scrape_item.parent_threads)} parent thread(s)"
            origin, parent = (scrape_item.parents[0], scrape_item.parents[-1]) if scrape_item.parents else (None, None)
            msg = (
                f"Skipping nested thread URL with {threads}:"
                f"URL: {scrape_item.url}\n"
                f"Parent:  {parent}\n"
                f"Origin:  {origin}\n"
            )
            raise MaxChildrenError(msg)

        self._limit_nexted_thread_folders(scrape_item)

    @final
    def _limit_nexted_thread_folders(self, scrape_item: ScrapeItem) -> None:
        if self.max_thread_folder_depth is None:
            return
        n_parents = len(scrape_item.parent_threads)
        if n_parents > self.max_thread_folder_depth:
            scrape_item.folders.pop()
            if not self.separate_posts:
                return
            scrape_item.folders.pop()

    @final
    def stop_thread_recursion(self, scrape_item: ScrapeItem) -> bool:
        if n_parents := len(scrape_item.parent_threads):
            if n_parents > self.max_thread_depth:
                return True

            return not (self.SUPPORTS_THREAD_RECURSION and self.max_thread_depth)

        return False

    @final
    @error_handling_wrapper
    async def handle_link(self, scrape_item: ScrapeItem, link: AbsoluteHttpURL) -> None:
        if link == self.PRIMARY_URL:
            return None
        if self.is_attachment(link):
            return await self.handle_internal_link(scrape_item, link)
        if self.PRIMARY_URL.host == link.host:
            self.create_task(self.run(scrape_item.create_child(link)))
            return None
        new_scrape_item = scrape_item.create_child(link)
        self.handle_external_links(new_scrape_item)
        scrape_item.add_children()

    # TODO: Move this to the base crawler
    # TODO: Define an unified workflow for crawlers to perform and check login
    @final
    @error_handling_wrapper
    async def login(self, login_url: AbsoluteHttpURL) -> None:
        session_cookie = self.cookies.get(self.LOGIN_USER_COOKIE_NAME)
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
        text = await self.request_text(login_url)
        logged_in = '<span class="p-navgroup-user-linkText">' in text or "You are already logged in." in text
        return text, logged_in

    @classmethod
    def is_thumbnail(cls, link: AbsoluteHttpURL) -> bool:
        assert link
        return False

    @classmethod
    def thumbnail_to_img(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL | None:
        assert url
        return None

    @classmethod
    def parse_thread(cls, url: AbsoluteHttpURL, thread_name_and_id: str) -> Thread:
        return parse_thread(url, thread_name_and_id, cls.PAGE_URL_PART_NAME, cls.POST_URL_PART_NAME)

    @classmethod
    def make_post_url(cls, thread: Thread, post_id: int) -> AbsoluteHttpURL:
        return thread.url / f"{cls.POST_URL_PART_NAME}-{post_id}"

    @error_handling_wrapper
    async def thread(self, scrape_item: ScrapeItem, /, thread: Thread) -> None:
        scrape_item.setup_as_forum("")
        if thread.url in self.scraped_threads:
            return

        scrape_item.parent_threads.add(thread.url)
        await self._thread(scrape_item, thread)

    async def _thread(self, scrape_item: ScrapeItem, thread: Thread) -> None:
        first_page, pages = await aio.peek_first(self.web_pager(scrape_item.url, self.get_next_page))
        try:
            title = get_post_title(first_page, self.SELECTORS)
        except ScrapeError as e:
            self.log.debug("Got an unprocessable soup", exc_info=e)
            raise
        else:
            scrape_item.append_folders(self.create_title(title, thread_id=thread.id))

        post_url = None
        try:
            async for soup in pages:
                for post in self._iter_posts(thread, soup):
                    post_url = self.make_post_url(thread, post.id)
                    new_scrape_item = scrape_item.create_new(thread.url, add_parent=post_url)
                    new_scrape_item.uploaded_at = post.timestamp
                    self.create_task(self.post(new_scrape_item, post))
                    scrape_item.add_children()
        finally:
            if post_url and post_url != thread.url:
                self.manager.scrape_mapper.logs.write_last_forum_post(post_url)

    @classmethod
    def _resolve_spoiler_iframes(cls, soup: BeautifulSoup) -> None:
        for name in ("data-s9e-mediaembed",):
            attr = f"{name}-iframe"
            for span_iframe in soup.select(f"span[{name}]"):
                try:
                    data = json.loads(css.select(span_iframe, f"span[{attr}]", attr))
                except (css.SelectorError, ValueError):
                    continue

                if type(data) is not list or len(data) % 2 != 0:
                    cls.get_logger().warning("Unable to resolve iframe attributes: %s", data)
                    continue

                span_iframe.replace_with(soup.new_tag("iframe", attrs=dict(itertools.batched(data, 2))))

    def _iter_posts(self, thread: Thread, soup: BeautifulSoup) -> Generator[ForumPost]:
        self._resolve_spoiler_iframes(soup)
        for article in soup.select(self.SELECTORS.posts.article):
            post = ForumPost.new(article, self.SELECTORS.posts)
            if thread.post_id and post.id < thread.post_id:
                continue

            yield post

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post: ForumPost) -> None:
        scrape_item.setup_as_post("")
        post_title = self.create_separate_post_title(None, str(post.id), post.date)
        scrape_item.append_folders(post_title)
        stats: dict[str, int] = {}

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            for scraper in (
                self._attachments,
                self._images,
                self._videos,
                self._external_links,
                self._embeds,
                self._lazy_load_embeds,
            ):
                for url in scraper(post):
                    scraper_name = scraper.__name__.removeprefix("_")
                    stats[scraper_name] = stats.get(scraper_name, 0) + 1
                    tg.create_task(self.process_child(scrape_item, url, embeds="embeds" in scraper_name))
                    scrape_item.add_children()
                    await sleep()

        if stats:
            self.log.info("post #%s stats = %s", post.id, stats)

    @classmethod
    def _external_links(cls, post: ForumPost) -> Iterable[str]:
        selector = cls.SELECTORS.posts.links
        links = css.iselect(post.content, selector.element)
        valid_links = (link for link in links if not cls.is_username_or_attachment(link))
        return iter_links(valid_links, selector.attribute)

    @classmethod
    def _images(cls, post: ForumPost) -> Iterable[str]:
        selector = cls.SELECTORS.posts.a_tag_w_image if cls.IGNORE_EMBEDED_IMAGES_SRC else cls.SELECTORS.posts.images
        images = css.iselect(post.content, selector.element)
        return iter_links(images, selector.attribute)

    @classmethod
    def _videos(cls, post: ForumPost) -> Iterable[str]:
        selector = cls.SELECTORS.posts.videos
        videos = css.iselect(post.content, selector.element)
        return iter_links(videos, selector.attribute)

    @classmethod
    def _attachments(cls, post: ForumPost) -> Iterable[str]:
        selector = cls.SELECTORS.posts.attachments
        attachments = css.iselect(post.article, selector.element)
        return iter_links(attachments, selector.attribute)

    @classmethod
    def _embeds(cls, post: ForumPost) -> Iterable[str]:
        selector = cls.SELECTORS.posts.embeds
        embeds = css.iselect(post.content, selector.element)
        return iter_links(embeds, selector.attribute)

    @classmethod
    def _lazy_load_embeds(cls, post: ForumPost) -> Iterable[str]:
        selector = cls.SELECTORS.posts.lazy_load_embeds
        for lazy_media in css.iselect(post.content, selector.element):
            yield extr_text(css.attr(lazy_media, selector.attribute), "loadMedia(this, '", "')")

    def get_next_page(self, soup: BeautifulSoup) -> str | None:
        try:
            return css.select(soup, *self.SELECTORS.next_page)
        except css.SelectorError:
            return None

    @final
    @error_handling_wrapper
    async def process_child(self, scrape_item: ScrapeItem, link_str: str, *, embeds: bool = False) -> None:
        link_str_ = pre_process_child(link_str, embeds=embeds)
        if not link_str_:
            return None
        link = await self.get_absolute_link(link_str_)
        if not link:
            return None
        if self.is_thumbnail(link):
            link = self.thumbnail_to_img(link)
            if not link:
                return self.log.info(f"Skipping thumbnail: {link}")
        await self.handle_link(scrape_item, link)

    async def get_absolute_link(self, link: str | AbsoluteHttpURL) -> AbsoluteHttpURL | None:
        absolute_link = link if type(link) is AbsoluteHttpURL else self.parse_url(clean_link_str(link))
        if is_confirmation_link(absolute_link):
            return await self.resolve_confirmation_link(absolute_link)
        return absolute_link

    @error_handling_wrapper
    async def resolve_confirmation_link(self, link: AbsoluteHttpURL) -> AbsoluteHttpURL | None:

        if b64_url := link.query.get("url") or link.query.get("to"):
            url = base64.urlsafe_b64decode(b64_pad(b64_url)).decode("utf-8")
        else:
            url = link.query.get("u")

        if url and url.startswith("https://"):
            return self.parse_url(url)

        soup = await self.request_soup(link)
        selector = self.SELECTORS.confirmation_button
        confirm_button = soup.select_one(selector.element)
        if not confirm_button:
            return None

        link_str: str = css.attr(confirm_button, selector.attribute)
        link_str = link_str.split('" class="link link--internal', 1)[0]
        new_link = self.parse_url(link_str)
        return await self.get_absolute_link(new_link)

    @error_handling_wrapper
    async def handle_internal_link(self, scrape_item: ScrapeItem, link: AbsoluteHttpURL | None = None) -> None:
        link = link or scrape_item.url
        slug = link.name or link.parent.name
        if slug.isdigit():
            return await self.follow_redirect(scrape_item.create_new(link))

        filename, ext = self.get_filename_and_ext(link.name)
        new_scrape_item = scrape_item.copy()
        new_scrape_item.append_folders("Attachments")
        new_scrape_item.part_of_album = True
        await self.handle_file(link, new_scrape_item, filename, ext)

    @classmethod
    def is_username_or_attachment(cls, link_obj: Tag) -> bool:
        if link_obj.select_one(".username"):
            return True
        try:
            if link_str := css.attr(link_obj, cls.SELECTORS.posts.links.element):
                return cls.is_attachment(link_str)
        except Exception:  # noqa: BLE001
            pass
        return False


def iter_links(links: Iterable[Tag], attribute: str) -> Iterable[str]:
    for link_tag in links:
        try:
            yield css.attr(link_tag, attribute)
        except Exception:  # noqa: BLE001, S112
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
    match link.parts[1:]:
        case ["ads", "go", *_] if link.query.get("u"):
            return True
        case _:
            return (
                "masked" in link.parts
                or "link-confirmation" in link.path
                or ("redirect" in link.parts and "to" in link.query)
            )


def pre_process_child(link_str: str, *, embeds: bool = False) -> str | None:
    assert isinstance(link_str, str)
    if embeds:
        link_str = extract_embed_url(link_str)

    if link_str and not is_blob_or_svg(link_str):
        return link_str
