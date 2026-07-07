"""General crawler for all wordpress sites

Reference: https://developer.wordpress.org/rest-api/reference/#rest-api-developer-endpoint-reference
"""

from __future__ import annotations

import datetime
import itertools
import re
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, final

from bs4 import BeautifulSoup

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css, open_graph
from cyberdrop_dl.utils.errors import error_handling_wrapper

from .models import HTML, Category, CategorySequence, ColletionType, Post, PostSequence, Tag, TagSequence

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Iterable

    import yarl

    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem


_POST_PER_REQUEST = 100
_HTTP_URL_REGEX = re.compile(
    r"https?://(www\.)?[-a-zA-Z0-9@:%._+~#=]{2,256}\.[a-z]{2,12}\b([-a-zA-Z0-9@:%_+.~#?&/=]*)"
)  # Same as Xenforo
_EXT_REGEX = re.compile(r"\d{2,}x\d{2,}(\.\w+)?")


_Selector = css.CssAttributeSelector


class Selector:
    POST_TITLE: str = "#content .single-post-title"
    POST_CONTENT: str = "#content .entry-content"
    POST_ID: _Selector = _Selector("[id*='post-']", "id")
    IMG: _Selector = _Selector("img[class*='wp-image']", "srcset")
    POST_LINK_FROM_PAGE: _Selector = _Selector(".post a[href]", "href")
    NEXT_PAGE: _Selector = _Selector("a.page-numbers.next", "href")


_POST_ID_REGEX = re.compile(r"(?:postid-|post-)(\d+)")


class WordPressBaseCrawler(Crawler, is_abc=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Category": "/category/<category_slug>",
        "Tag": "/tag/<tag_slug>",
        "Post": "/<post_slug>/",
        "All Posts": "/posts/",
        "Date Range": (
            "...?before=<date>",
            "...?after=<date>",
            "...?before=<date&after=<date>",
        ),
        "**NOTE**": """

        For `Date Range`, <date>  must be a valid iso 8601 date, ex: `2022-12-06`.

        `Date Range` can be combined with `Category`, `Tag` and `All Posts`.
        ex: To only download categories from a date range: ,
        `/category/<category_slug>?before=<date>`""",
    }
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date} - {id} - {title}"
    WP_USE_REGEX: ClassVar[bool] = True
    SUPPORTS_THREAD_RECURSION: ClassVar[bool] = False
    _RATE_LIMIT: ClassVar[RateLimit] = 3, 1

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        assert cls.fetch is WordPressBaseCrawler.fetch

    @final
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        scrape_item.url = scrape_item.url.with_query(None)
        match scrape_item.url.parts[1:]:
            case ["posts"]:
                return await self.all_posts(scrape_item)
            case [ColletionType.CATEGORY.value, _]:
                return await self.category_or_tag(scrape_item, ColletionType.CATEGORY)
            case [ColletionType.TAG.value, _]:
                return await self.category_or_tag(scrape_item, ColletionType.TAG)
            case ["wp-json", *_]:
                raise ValueError
            case _:
                if _match_date_from_path(scrape_item.url.parts[1:]):
                    # TODO: Handle this
                    raise ValueError
                return await self.post(scrape_item)

    @property
    @final
    def separate_posts(self) -> bool:
        # For wordpress we should always create a separate folder. Each post is an individual page
        return True

    @staticmethod
    @final
    def is_attachment(url: AbsoluteHttpURL) -> bool:
        return "wp-content" in url.parts and bool(url.suffix)

    @abstractmethod
    async def category_or_tag(self, scrape_item: ScrapeItem, /, colletion_type: ColletionType) -> None: ...

    @abstractmethod
    async def post(self, scrape_item: ScrapeItem, /) -> None: ...

    @abstractmethod
    async def all_posts(self, scrape_item: ScrapeItem, /) -> None: ...

    @final
    async def _filter_post(self, scrape_item: ScrapeItem, post: Post) -> None:
        new_scrape_item = scrape_item.create_child(self.parse_url(post.link))
        await self._handle_post(new_scrape_item, post)
        scrape_item.add_children()

    @final
    async def _handle_post(self, scrape_item: ScrapeItem, post: Post, *, is_single_post: bool = False) -> None:
        post_id = str(post.id)
        title = self.create_separate_post_title(post.title, post_id, post.date_gmt.date())
        if is_single_post:
            title = self.create_title(title)
        scrape_item.setup_as_album(title, album_id=post_id)
        scrape_item.upload_date = post.date_gmt
        if post.thumbnail:
            await self.direct_file(scrape_item, self.parse_url(post.thumbnail))
        return await self._post_content(scrape_item, post)

    @final
    async def _handle_link(self, scrape_item: ScrapeItem, link: AbsoluteHttpURL) -> None:
        if self.is_attachment(link):
            return await self.direct_file(scrape_item, link)
        if self.PRIMARY_URL.host == link.host:
            return None
        new_scrape_item = scrape_item.create_new(link)
        self.handle_external_links(new_scrape_item)
        scrape_item.add_children()

    async def _post_content(self, scrape_item: ScrapeItem, post: Post) -> None:
        for link in self.iter_parse_url(_iter_links(post.content, use_regex=self.WP_USE_REGEX)):
            if link:
                await self._handle_link(scrape_item, link)

    @classmethod
    def parse_url(
        cls,
        url: yarl.URL | str,
        /,
        relative_to: AbsoluteHttpURL | None = None,
        *,
        trim: bool | None = None,
    ) -> AbsoluteHttpURL:
        # TODO: handle more domains and move it to the base crawler
        link = _get_original_quality_link(str(url))
        url = super().parse_url(link, relative_to, trim=trim)
        if url.host == "ouo.io" and (redirect_url := url.query.get("s")):
            return super().parse_url(redirect_url)
        return url

    @final
    def iter_parse_url(self, iterable: Iterable[str]) -> Iterable[AbsoluteHttpURL]:
        for link_str in dict.fromkeys(iterable):
            try:
                yield self.parse_url(link_str)
            except Exception:  # noqa: BLE001, S112
                continue


class WordPressMediaCrawler(WordPressBaseCrawler, is_generic=True):
    WP_CATEGORIES_ENDPOINT: ClassVar[str] = "/wp-json/wp/v2/categories"
    WP_TAGS_ENDPOINT: ClassVar[str] = "/wp-json/wp/v2/tags"
    WP_POSTS_ENDPOINT: ClassVar[str] = "/wp-json/wp/v2/posts"

    def __init_subclass__(cls, *, is_abc: bool = False, **kwargs: Any) -> None:
        super().__init_subclass__(is_abc=is_abc, **kwargs)
        if is_abc:
            return
        cls.WP_API_CATEGORIES_URL = cls.PRIMARY_URL / cls.WP_CATEGORIES_ENDPOINT.removeprefix("/")
        cls.WP_API_TAGS_URL = cls.PRIMARY_URL / cls.WP_TAGS_ENDPOINT.removeprefix("/")
        cls.WP_API_POSTS_URL = cls.PRIMARY_URL / cls.WP_POSTS_ENDPOINT.removeprefix("/")

    @error_handling_wrapper
    async def category_or_tag(self, scrape_item: ScrapeItem, colletion_type: ColletionType) -> None:
        if colletion_type is ColletionType.CATEGORY:
            model, api_url = CategorySequence, self.WP_API_CATEGORIES_URL.with_query(slug=scrape_item.url.name)
        else:
            model, api_url = TagSequence, self.WP_API_TAGS_URL.with_query(slug=scrape_item.url.name)

        collections = model.validate_json(await self.request_text(api_url))
        if not collections:
            raise ScrapeError(404)
        await self.__collection(scrape_item, collections[0])

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem) -> None:
        api_url = self.WP_API_POSTS_URL.with_query(slug=scrape_item.url.name)
        posts = PostSequence.validate_json(await self.request_text(api_url))
        if not posts:
            raise ScrapeError(404)
        return await self._handle_post(scrape_item, posts[0], is_single_post=True)

    @error_handling_wrapper
    async def all_posts(self, scrape_item: ScrapeItem) -> None:
        api_url = self.WP_API_POSTS_URL
        scrape_item.setup_as_profile(self.create_title("Posts"))
        async for post in self._post_pager(api_url):
            await self._filter_post(scrape_item, post)

    async def __collection(self, scrape_item: ScrapeItem, collection: Category | Tag) -> None:
        title = self.create_title(f"{collection.description or collection.slug} [{collection._type}]")
        scrape_item.setup_as_profile(title)
        assert collection.id
        api_url = self.WP_API_POSTS_URL.with_query({collection._type: collection.id})
        async for post in self._post_pager(api_url):
            await self._filter_post(scrape_item, post)

    async def _post_pager(self, url: AbsoluteHttpURL, init_page: int | None = None) -> AsyncIterable[Post]:
        for page in itertools.count(init_page or 1):
            n_post = 0
            api_url = url.update_query(per_page=_POST_PER_REQUEST, page=page)
            for post in PostSequence.validate_json(await self.request_text(api_url)):
                n_post += 1
                yield post
            if n_post < _POST_PER_REQUEST:
                break
        else:
            raise ScrapeError(404)


class WordPressHTMLCrawler(WordPressBaseCrawler, is_generic=True):
    async def __make_request(self, api_url: AbsoluteHttpURL) -> BeautifulSoup:
        return await self.request_soup(api_url)

    @error_handling_wrapper
    async def category_or_tag(self, scrape_item: ScrapeItem, colletion_type: ColletionType) -> None:
        if colletion_type is ColletionType.CATEGORY:
            collection = Category(slug=scrape_item.url.name, link=str(scrape_item.url))
        else:
            collection = Tag(slug=scrape_item.url.name, link=str(scrape_item.url))
        await self.__handle_collection(scrape_item, collection)

    async def __handle_collection(self, scrape_item: ScrapeItem, collection: Category | Tag) -> None:
        title = self.create_title(f"{collection.description or collection.slug} [{collection._type}]")
        scrape_item.setup_as_profile(title)
        await self._post_pager(scrape_item)

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem) -> None:
        soup = await self.__make_request(scrape_item.url)
        post = self._parse_post(scrape_item, soup)
        return await self._handle_post(scrape_item, post, is_single_post=True)

    def _parse_post(self, scrape_item: ScrapeItem, soup: BeautifulSoup) -> Post:
        title = open_graph.get_title(soup) or css.select_text(soup, Selector.POST_TITLE)
        date = open_graph.get("published_time", soup) or _match_date_from_path(scrape_item.url.parts[1:4])
        data = {
            "id": get_post_id(soup),
            "slug": scrape_item.url.name,
            "title": title,
            "date_gmt": date,
            "link": str(scrape_item.url),
            "content": str(css.select(soup, Selector.POST_CONTENT)),
        }
        return Post.model_validate(data, by_name=True)

    @error_handling_wrapper
    async def all_posts(self, scrape_item: ScrapeItem) -> None:
        scrape_item.setup_as_profile(self.create_title("Posts"))
        await self._post_pager(scrape_item)

    async def _post_pager(self, scrape_item: ScrapeItem) -> None:
        async for soup in self.web_pager(scrape_item.url):
            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.POST_LINK_FROM_PAGE.element):
                self.create_task(self.run(new_scrape_item))


def _match_date_from_path(url_parts: tuple[str, ...]) -> datetime.datetime | None:
    match url_parts:
        case [year, month, day]:
            try:
                return datetime.datetime(int(year), int(month), int(day), tzinfo=datetime.UTC)
            except Exception:  # noqa: BLE001
                return None
        case _:
            return None


def _get_original_quality_link(link: str) -> str:
    stem, _, tail = link.rpartition("-")
    if match := re.search(_EXT_REGEX, tail):
        return f"{stem}.{match.group()}"
    return link


def _iter_links(html: HTML, *, use_regex: bool) -> Iterable[str]:
    soup = BeautifulSoup(html, "html.parser")
    images = css.iselect(soup, *css.images)
    iframes = css.iselect(soup, *css.iframes)
    if use_regex:
        regex = (match.group() for match in re.finditer(_HTTP_URL_REGEX, html))
        return itertools.chain(images, iframes, regex)
    return itertools.chain(images, iframes)


def get_post_id(soup: BeautifulSoup) -> int:
    id_text = Selector.POST_ID(soup)
    if match := _POST_ID_REGEX.search(id_text):
        post_id = match.group(1)
        for trash in ("post", "id", "-"):
            post_id = post_id.removeprefix(trash)
        return int(post_id)
    raise ValueError
