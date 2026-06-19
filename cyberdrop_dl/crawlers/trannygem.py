from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler, KVSVideo, extract_kvs_video
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem

if TYPE_CHECKING:
    from bs4 import BeautifulSoup


class TrannyGemCrawler(KernelVideoSharingCrawler, ensure_trailing_slash=True):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.trannygem.com")
    DOMAIN: ClassVar[str] = "trannygem"
    FOLDER_DOMAIN: ClassVar[str] = "TrannyGem"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["videos", *_]:
                return await self.video(scrape_item)
            case _:
                raise ValueError

    def _extract_video_params(self, soup: BeautifulSoup) -> tuple[KVSVideo, str, str]:
        video = extract_kvs_video(self, soup)
        filename, ext = self.get_filename_and_ext(video.url.name)

        # The path of the video URL is missing a trailing slash. Without it we get a 404 error.
        video.url = video.url.with_path(video.url.path + "/", keep_query=True, keep_fragment=True)
        return video, filename, ext
