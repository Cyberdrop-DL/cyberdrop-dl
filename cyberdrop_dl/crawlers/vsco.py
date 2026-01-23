from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic.alias_generators import to_snake

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class VSCOCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Media": (
            "/<user>/media/<media_id>",
            "/<user>/video/<media_id>",
        ),
        "Gallery": "/<user>/gallery",
    }

    DOMAIN: ClassVar[str] = "vsco"
    FOLDER_DOMAIN: ClassVar[str] = "VSCO"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vsco.co")
    _api_token: str = ""

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [user, "gallery"]:
                return await self.gallery(scrape_item, user)
            case [user, "media" | "video" as type_, media_id]:
                return await self.media(scrape_item, user, type_, media_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def media(self, scrape_item: ScrapeItem, user: str, type_: str, id_: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        scrape_item.setup_as_profile(self.create_title(user))
        state = await self._get_preloaded_state(scrape_item.url)
        file = state["medias"]["byId"][id_]["media"]
        file["type"] = "image" if type_ == "media" else type_
        await self._file(scrape_item, file)

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, user: str) -> None:
        scrape_item.setup_as_profile(self.create_title(user))
        state = await self._get_preloaded_state(scrape_item.url)
        site_id: int = state["sites"]["siteByUsername"][user]["site"]["id"]
        if not self._api_token:
            self._api_token = state["users"]["currentUser"]["tkn"]

        url = (self.PRIMARY_URL / "api/3.0/medias/profile").with_query(site_id=site_id, limit=20, cursor="")
        async for state in self._api_pager(url):
            for media in state["media"]:
                file = media[media["type"]]
                file["type"] = media["type"]
                # The file method will override with the proper URL
                new_item = scrape_item.create_child(scrape_item.url)
                self.create_task(self._file(new_item, file))
                scrape_item.add_children()

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: dict[str, Any]) -> None:
        file = {to_snake(key): value for key, value in file.items()}
        file["id"] = file.get("id") or file["_id"]
        scrape_item.possible_datetime = (file.get("upload_date") or file["created_date"]) // 1000
        if file["type"] == "image":
            return await self._image(scrape_item, file)
        await self._video(scrape_item, file)

    async def _image(self, scrape_item: ScrapeItem, img: dict[str, Any]) -> None:
        scrape_item.url = self.parse_url(img["permalink"])
        src_url = self.parse_url("https://" + img["responsive_url"])
        filename = self.create_custom_filename(img["id"], src_url.suffix)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            src_url.name,
            src_url.suffix,
            debrid_link=src_url,
            custom_filename=filename,
            metadata=img,
        )

    async def _video(self, scrape_item: ScrapeItem, video: dict[str, Any]) -> None:
        scrape_item.url = self.PRIMARY_URL / scrape_item.url.parts[1] / "video" / video["id"]
        url = self.parse_url(video["playback_url"])
        m3u8 = res = None
        ext = url.suffix
        if ext == ".m3u8":
            if await self.check_complete_from_referer(scrape_item):
                return

            ext = ".mp4"
            m3u8, info = await self.get_m3u8_from_playlist_url(url)
            res = info.resolution

        name, ext = self.get_filename_and_ext(video["id"] + ext)
        filename = self.create_custom_filename(video["id"], ext, resolution=res)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            name,
            ext,
            m3u8=m3u8,
            custom_filename=filename,
            metadata=video,
        )

    async def _get_preloaded_state(self, url: AbsoluteHttpURL) -> dict[str, Any]:
        soup = await self.request_soup(url, impersonate=True)
        script = css.select_text(soup, "script:-soup-contains('window.__PRELOADED_STATE__')")
        js = script[script.find("{") : script.rfind("}") + 1]
        return json.loads(js.replace('":undefined', '":null'))

    async def _api_pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[dict[str, Any]]:
        while True:
            data: dict[str, Any] = await self.request_json(
                url,
                headers={
                    "Authorization": f"Bearer {self._api_token}",
                    "X-Client-Platform": "web",
                    "X-Client-Build": "1",
                },
                impersonate=True,
            )
            yield data

            next_cursor = data.get("next_cursor")
            if not next_cursor:
                break

            url = url.update_query(cursor=next_cursor)
