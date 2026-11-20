from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, json_ld, unique
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    USERNAME = "p.author-header__username"
    ALBUM_TITLE = "h1.album-page-title"
    DATE = "span.date-time"
    IMAGE_BLOCK = "#album-images .image-block[data-key]"
    POSTS = "div.posts .list-view .item .post"
    POST_TITLE = "h2.p-title a.post-title"
    POST_BLOCK = ".post-expand-wrapper .post-block"
    IMAGE = ".main-image-wrapper"
    NEXT_PAGE = "li[class=next] a"


class PimpAndHostCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/album/<album_id>",
        "Image": "/image/<image_id>",
        "Post": "/p/<slug>-<post-id>",
        "User albums": "/album/user/<user_id>",
        "User posts": "/u/<user_id>/posts",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pimpandhost.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    DOMAIN: ClassVar[str] = "pimpandhost"
    FOLDER_DOMAIN: ClassVar[str] = "PimpAndHost"

    @override
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["album", "user", _user_id, *_]:
                await self.user_albums(scrape_item)
            case ["album", album_id, *_] if album_id.isdecimal():
                await self.album(scrape_item, album_id)
            case ["image", _]:
                await self.image(scrape_item)
            case ["p", slug] if "-" in slug:
                post_id = slug.rpartition("-")[-1]
                await self.post(scrape_item, post_id)
            case ["u", _user_id, "posts"]:
                await self.user_posts(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def user_albums(self, scrape_item: ScrapeItem) -> None:
        soup, pages = await aio.peek_next(self.web_pager(scrape_item.url))
        user = css.select_text(soup, Selector.USERNAME)
        scrape_item.setup_as_profile(self.create_title(f"{user} [user]"))

        sleep = aio.periodic_sleep(10)
        async for soup in pages:
            for album_id in unique(css.iselect(soup, Selector.IMAGE_BLOCK, "data-key")):
                new_item = scrape_item.create_child(self.PRIMARY_URL / "album" / album_id)
                self.create_task(self.run(new_item))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def user_posts(self, scrape_item: ScrapeItem) -> None:
        soup, pages = await aio.peek_next(self.web_pager(scrape_item.url))
        user = css.select_text(soup, Selector.USERNAME)
        scrape_item.setup_as_profile(self.create_title(f"{user} [user]"))

        sleep = aio.periodic_sleep(10)
        async for soup in pages:
            for post in css.iselect(soup, Selector.POSTS):
                url = self.parse_url(css.select(post, Selector.POST_TITLE, "href"))
                self.create_task(self.run(scrape_item.create_child(url)))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup, pages = await aio.peek_next(self.web_pager(scrape_item.url))
        name = css.select_text(soup, Selector.ALBUM_TITLE)
        title = self.create_title(name, album_id, force_album_id=name == "Untitled")
        scrape_item.setup_as_album(title, album_id=album_id)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for soup in pages:
                for image_id in unique(css.iselect(soup, Selector.IMAGE_BLOCK, "data-key")):
                    new_item = scrape_item.create_child(self.PRIMARY_URL / "image" / image_id)
                    tg.create_task(self._image_task(new_item))
                    scrape_item.add_children()
                    await sleep()

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        soup, pages = await aio.peek_next(self.web_pager(scrape_item.url))
        title = self.create_title(css.select_text(soup, Selector.POST_TITLE), post_id)
        scrape_item.setup_as_album(title, album_id=post_id)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for soup in pages:
                for block in css.iselect(soup, Selector.POST_BLOCK):
                    match dt := css.attr(block, "data-type"):
                        case "image":
                            img = self.parse_url(css.select(block, "img[src]", "src"))
                            tg.create_task(self.direct_file(scrape_item, img))
                            scrape_item.add_children()
                            await sleep()
                        case "text":
                            for link in self.iter_urls(block, "a", "href"):
                                self.handle_external_links(scrape_item.create_child(link))
                                scrape_item.add_children()
                                await sleep()
                        case _:
                            raise ScrapeError(422, f"Unsupported post block type = {dt}")

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        src = self.parse_url(css.select(soup, Selector.IMAGE, "data-src"))
        scrape_item.uploaded_at = json_ld.date_published(soup)
        filename, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(src, scrape_item, filename, ext)

    _image_task = auto_task_id(image)
