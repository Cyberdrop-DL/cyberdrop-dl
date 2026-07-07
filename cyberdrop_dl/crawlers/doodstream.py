from __future__ import annotations

import dataclasses
import random
import string
import time
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    VIDEO = "div#video_player video"
    MD5_JS = "script:-soup-contains('/pass_md5/')"
    FILE_ID_JS = "script:-soup-contains('file_id')"


@dataclasses.dataclass(slots=True)
class Video:
    id: str
    title: str
    dl_link: AbsoluteHttpURL


class DoodStreamCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/e/<video_id>",
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
    UPDATE_UNSUPPORTED: ClassVar[bool] = True
    DOMAIN: ClassVar[str] = "doodstream"
    FOLDER_DOMAIN: ClassVar[str] = "DoodStream"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["e", _, *_]:
                return await self.video(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        canonical_url = scrape_item.url.with_host(self.PRIMARY_URL.host)
        if await self.check_complete_from_referer(canonical_url):
            return

        video = await self._get_video_info(scrape_item.url)
        filename, ext = self.get_filename_and_ext(f"{video.id}.mp4")
        custom_filename = self.create_custom_filename(video.title, ext, file_id=video.id)
        scrape_item.url = canonical_url

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
