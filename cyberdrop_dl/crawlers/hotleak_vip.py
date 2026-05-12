from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from typing_extensions import override

from cyberdrop_dl.crawlers.leakedzone import LeakedZoneCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css

if TYPE_CHECKING:
    from bs4 import BeautifulSoup


LIGHT_GALLERY_ITEM_SELECTOR = "div.light-gallery-item"


class HotLeakVipCrawler(LeakedZoneCrawler):
    DOMAIN: ClassVar[str] = "hotleak.vip"
    FOLDER_DOMAIN: ClassVar[str] = "HotLeakVip"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://hotleak.vip")
    IMAGES_CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://image-cdn.hotleak.vip")

    @override
    @classmethod
    def _extract_video(cls, soup: BeautifulSoup) -> str:
        video_info_text = css.select(soup, LIGHT_GALLERY_ITEM_SELECTOR, "data-video")
        video_data: dict[str, Any] = json.loads(video_info_text)
        return video_data["source"][0]["src"]
