from __future__ import annotations

import random
import string
import time
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text
from cyberdrop_dl.utils.dataclass import struct
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    VIDEO = "div#video_player video"
    MD5_JS = "script:-soup-contains('/pass_md5/')"
    FILE_ID_JS = "script:-soup-contains('file_id')"


@struct
class Video:
    id: str
    title: str
    dl_link: AbsoluteHttpURL


@HTTPConfig(impersonate=True)
class DoodStreamCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/e/<video_id>",
            "/v/<video_id>",
            "/d/<video_id>",
        ),
        "Folder": "/f/<folder_id>",
    }
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "all3do.com",
        "d000d.com",
        "do7go.com",
        "dood.re",
        "dood.yt",
        "doodcdn",
        "doodstream.co",
        "doodstream",
        "myvidplay.com",
        "playmogo.com",
        "vidply.com",
        "dooodster.com",
    )
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://doodstream.com/")
    DOMAIN: ClassVar[str] = "doodstream"
    FOLDER_DOMAIN: ClassVar[str] = "DoodStream"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["e" | "v" | "d", video_id, *_]:
                await self.video(scrape_item, video_id)
            case ["f", folder_id, *_]:
                await self.folder(scrape_item, folder_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def folder(self, scrape_item: ScrapeItem, folder_id: str) -> None:
        async with self.request(scrape_item.url) as resp:
            scrape_item.url = resp.url
            soup = await resp.soup()

        title = css.select_text(soup, "h1")
        scrape_item.setup_as_album(self.create_title(title, folder_id), album_id=folder_id)

        downloaded = await self.get_completed_by_album(folder_id)
        sleep = aio.periodic_sleep(10)
        for url in self.iter_urls(soup, ".search-files li a.btn"):
            if url in downloaded:
                continue
            self.create_task(self.run(scrape_item.create_child(url)))
            await sleep()

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        embed_url = self.PRIMARY_URL / "e" / video_id
        if await self.check_complete(embed_url):
            return

        video = await self._get_video_info(embed_url)
        filename, ext = self.get_filename_and_ext(f"{video.id}.mp4")
        custom_filename = self.create_custom_filename(video.title, ext, file_id=video.id)
        scrape_item.url = embed_url

        await self.handle_file(
            scrape_item.url,
            scrape_item,
            filename,
            ext,
            debrid_link=video.dl_link,
            custom_filename=custom_filename,
        )

    async def _get_video_info(self, url: AbsoluteHttpURL) -> Video:
        async with self.request(url, impersonate=True) as resp:
            soup = await resp.soup()

        api_url = resp.url.origin() / "pass_md5" / _md5_pass(soup)
        download_url = await self.request_text(api_url, impersonate=True)
        return Video(
            id=_file_id(soup),
            title=css.page_title(soup, "DoodStream"),
            dl_link=self.parse_url(download_url + _random_padding()).with_query(
                token=api_url.name,
                expiry=int(time.time() * 1000),
            ),
        )


def _md5_pass(soup: BeautifulSoup) -> str:
    js_text = css.select_text(soup, Selector.MD5_JS)
    return extr_text(js_text, "/pass_md5/", "'")


def _file_id(soup: BeautifulSoup) -> str:
    js_text = css.select_text(soup, Selector.FILE_ID_JS)
    _, file_id, _ = js_text.split("'file_id'")[-1].split("'", 2)
    return file_id


def _random_padding() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=10))
