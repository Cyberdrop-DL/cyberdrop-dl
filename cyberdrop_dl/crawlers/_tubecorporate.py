from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem


class TubeCorporateCrawler(Crawler, is_abc=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/videos/<video_id>/...",
            "/embed/<video_id>/...",
        )
    }

    def __init_subclass__(cls, **kwargs: Any) -> None:
        domains = cls.PRIMARY_URL.host, *cls.SUPPORTED_DOMAINS
        domains = *domains, *(d.replace(".com", ".tube") for d in domains)
        old_domains = *cls.OLD_DOMAINS, *(d.replace(".com", ".tube") for d in cls.OLD_DOMAINS)
        cls.SUPPORTED_DOMAINS = tuple(sorted(set(domains)))
        cls.OLD_DOMAINS = tuple(sorted(set(old_domains)))
        super().__init_subclass__(**kwargs)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["videos" | "embed", video_id, *_]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        api_url = self._get_api_url(scrape_item, video_id)
        video = _choose_best_format(await self.request_json(api_url))
        video_info = await self._get_video_info(scrape_item, video_id)
        scrape_item.possible_datetime = self.parse_iso_date(video_info["post_date"])

        decoded_url = _decode_base64(video["video_url"])
        link = self.parse_url(decoded_url, relative_to=scrape_item.url.origin(), trim=False)
        filename, ext = self.get_filename_and_ext(video_id + ".mp4")
        custom_filename = self.create_custom_filename(video_info["title"], ext, file_id=video_id)

        return await self.handle_file(
            scrape_item.url,
            scrape_item,
            filename,
            ext,
            custom_filename=custom_filename,
            debrid_link=link,
            metadata=video_info,
        )

    async def _get_video_info(self, scrape_item: ScrapeItem, video_id: str) -> dict[str, str]:
        json_url = self._get_json_url(scrape_item, video_id)
        video_info: dict[str, dict[str, str]] = await self.request_json(json_url)
        return video_info["video"]

    def _get_json_url(self, scrape_item: ScrapeItem, video_id: str) -> AbsoluteHttpURL:
        slug = f"{int(1e6 * (int(video_id) // 1e6))}/{1000 * (int(video_id) // 1000)}"
        return scrape_item.url.with_path(f"api/json/video/86400/{slug}/{video_id}.json")

    def _get_api_url(self, scrape_item: ScrapeItem, video_id: str) -> AbsoluteHttpURL:
        query = {"video_id": video_id, "lifetime": "8640000"}
        return scrape_item.url.with_path("api/videofile.php").with_query(query)


def _choose_best_format(formats: list[dict[str, str]]) -> dict[str, str]:
    if len(formats) > 1:
        raise ScrapeError(422, "More than one format found")
    return formats[0]


def _decode_base64(text: str) -> str:
    return base64.b64decode(
        text.translate(
            text.maketrans(
                {
                    "\u0405": "S",
                    "\u0406": "I",
                    "\u0408": "J",
                    "\u0410": "A",
                    "\u0412": "B",
                    "\u0415": "E",
                    "\u041a": "K",
                    "\u041c": "M",
                    "\u041d": "H",
                    "\u041e": "O",
                    "\u0420": "P",
                    "\u0421": "C",
                    "\u0425": "X",
                    ",": "/",
                    ".": "+",
                    "~": "=",
                }
            )
        )
    ).decode()
