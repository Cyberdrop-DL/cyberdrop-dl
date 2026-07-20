from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar, final, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import TextExtractor, css, dates, parse_url
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    import datetime

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    MEDIA_INFO_JS = "script:-soup-contains('__fileurl')"
    MEDIA = "div.thumb-container a.img-container"
    COLLECTION_TITLE = ".gallery-title > h2, .group-bio > h1"
    USER_NAME = "div.member-bio-username"


class MotherlessCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Group": (
            "/g/<group_name>",
            "/gi/<group_name>",
            "/gv/<group_name>",
        ),
        "Gallery": (
            "/G<gallery_id>",
            "/GI<gallery_id>",
            "/GV<gallery_id>",
        ),
        "User": (
            "/m/<username>",
            "/member/<username>",
            "/u/<username>",
            "/u/<username>?t=v",
            "/u/<username>?t=i",
        ),
        "Image or Video": (
            "/<media_id>",
            "/g/<group_name>/<media_id>",
            "/G<gallery_id>/<media_id>",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://motherless.xxx")
    NEXT_PAGE_SELECTOR: ClassVar[str] = ".pagination_link > a[rel=next]"
    DOMAIN: ClassVar[str] = "motherless"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("motherless.com",)
    _RATE_LIMIT: ClassVar[RateLimit] = 2, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["g", slug]:
                await self.group(scrape_item, slug)
            case ["gv" | "gi" as prefix, slug]:
                name = "images" if prefix == "gi" else "videos"
                await self.collection(scrape_item, slug, name)

            case [slug] if slug.startswith("G") and (gallery_id := slug[2:]):
                if (prefix := slug[:2]) in ("GV", "GI"):
                    name = "images" if prefix == "GI" else "videos"
                    return await self.collection(scrape_item, gallery_id, name)

                gallery_id = slug[1:]
                await self.gallery(scrape_item, gallery_id)

            case [media_id]:
                await self.media(scrape_item, media_id)

            case ["u", username]:
                type_ = scrape_item.url.query.get("t")
                if type_ not in ("v", "i"):
                    return await self.user(scrape_item, username)
                name = "images" if type_ == "i" else "videos"
                await self.user_uploads(scrape_item, username, name)

            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case [slug, media_id] if slug.startswith("G") and slug[1:]:
                return url.origin() / media_id
            case ["g", _, media_id]:
                return url.origin() / media_id
            case ["member" | "m", username]:
                return url.origin() / "u" / username
            case _:
                return url

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, gallery_id: str) -> None:
        for part in ("GI", "GV"):
            new_item = scrape_item.copy()
            new_item.url = self.PRIMARY_URL / f"{part}{gallery_id}"
            self.create_task(self.run(new_item))

    @error_handling_wrapper
    async def group(self, scrape_item: ScrapeItem, slug: str) -> None:
        for part in ("gi", "gv"):
            new_item = scrape_item.copy()
            new_item.url = self.PRIMARY_URL / part / slug
            self.create_task(self.run(new_item))

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, username: str) -> None:
        for part in ("i", "v"):
            new_item = scrape_item.copy()
            new_item.url = (self.PRIMARY_URL / "u" / username).with_query(t=part)
            self.create_task(self.run(new_item))

    @error_handling_wrapper
    async def user_uploads(self, scrape_item: ScrapeItem, username: str, name: str) -> None:
        scrape_item.setup_as_album(self.create_title(f"{username} [user]"))
        scrape_item.append_folders(name)

        soup, pages = await aio.peek_first(self.web_pager(scrape_item.url))
        _check_soup(soup)

        async for soup in pages:
            for new_item in self.iter_children(scrape_item, soup, Selector.MEDIA):
                self.create_eager_task(self.run(new_item))

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, collection_id: str, name: str) -> None:
        soup, pages = await aio.peek_first(self.web_pager(scrape_item.url))
        _check_soup(soup)
        title = self.create_title(css.select_text(soup, Selector.COLLECTION_TITLE), collection_id)
        scrape_item.setup_as_album(title, album_id=collection_id)
        scrape_item.append_folders(name)

        async for soup in pages:
            for new_item in self.iter_children(scrape_item, soup, Selector.MEDIA):
                self.create_eager_task(self.run(new_item))

    @error_handling_wrapper
    async def media(self, scrape_item: ScrapeItem, _media_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        _check_soup(soup)
        media = _extract_media(soup)
        scrape_item.upload_date = media.upload_date
        _, ext = self.get_filename_and_ext(media.url.name)
        filename = self.create_custom_filename(media.name, ext, file_id=media.code)
        await self.handle_file(media.url, scrape_item, media.name, ext, custom_filename=filename)


def _check_soup(soup: BeautifulSoup) -> None:
    html = soup.get_text()
    for txt in ("The page you're looking for cannot be found", "File not Found. Nothing to see here"):
        if txt in html:
            raise ScrapeError(404)
    if "The content you are trying to view is for friends only" in html:
        raise ScrapeError(401)


@dataclasses.dataclass(slots=True)
class Media:
    type: str
    code: str
    group: str
    name: str
    url: AbsoluteHttpURL
    upload_date: datetime.datetime


def _extract_media(soup: BeautifulSoup) -> Media:
    js_text = css.select_text(soup, Selector.MEDIA_INFO_JS)
    extract = TextExtractor(js_text)
    props = css.json_ld(soup, "uploadDate")
    return Media(
        name=props["name"],
        upload_date=dates.parse_iso(props["uploadDate"]),
        type=extract("__mediatype = '", "'"),
        code=extract("__codename = '", "'"),
        group=extract("__group = '", "'"),
        url=parse_url(extract("__fileurl = '", "'")),
    )
