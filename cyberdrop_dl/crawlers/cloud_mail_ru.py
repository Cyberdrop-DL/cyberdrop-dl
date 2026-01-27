from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper, get_text_between

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class CloudMailRuCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Public files / folders": "/public/<web_path>"}
    DOMAIN: ClassVar[str] = "cloud.mail.ru"
    FOLDER_DOMAIN: ClassVar[str] = DOMAIN
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cloud.mail.ru")
    SKIP_PRE_CHECK: ClassVar[bool] = True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["public", *rest] if rest:
                return await self.public(scrape_item, path="/".join(rest))
            case _:
                raise ValueError

    async def _request_info(self, path: str) -> dict[str, Any]:
        api_url = (self.PRIMARY_URL / "api/v4/public/list").with_query(
            weblink=path,
            sort="name",
            order="asc",
            offset=0,
            limit=500,
            version=4,
        )
        return await self.request_json(api_url)

    async def _get_dl_server(self, path: str) -> AbsoluteHttpURL:
        web_url = self.PRIMARY_URL / "public" / path
        html = await self.request_text(
            web_url,
            max_field_size=15_000,  # They send a really long header value for "Content-Security-Policy-Report-Only"
        )
        data = get_text_between(html, '"weblink_get":', "},")
        return self.parse_url(json.loads(data + "}")["url"])

    async def public(self, scrape_item: ScrapeItem, path: str) -> None:
        node = await self._request_info(path)
        is_file = node["type"] == "file"

        if is_file and await self.check_complete_from_referer(scrape_item):
            return

        node["_dl_server"] = await self._get_dl_server(path)
        if is_file:
            return await self._file(scrape_item, node)

        title = self.create_title(node["name"])
        scrape_item.setup_as_album(title, album_id=node["weblink"])
        await self._walk_folder(scrape_item, node)

    async def _walk_folder(self, scrape_item: ScrapeItem, root: dict[str, Any]) -> None:
        folder = root
        subfolders: list[str] = []

        while True:
            for node in folder["list"]:
                if node["type"] == "file":
                    web_url = self.PRIMARY_URL / "public" / node["weblink"]
                    new_item = scrape_item.create_child(web_url)
                    node["_dl_server"] = root["_dl_server"]
                    self.create_task(self._file(new_item, node))
                    scrape_item.add_children()

                elif (node["count"]["files"] + node["count"]["folders"]) > 0:
                    subfolders.append(node["weblink"])

            try:
                path = subfolders.pop()
                folder = await self._request_info(path)
            except IndexError:
                break

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: dict[str, Any]) -> None:
        for part in file["weblink"].split("/")[2:-1]:
            scrape_item.add_to_parent_title(part)

        dl_link = file["_dl_server"] / file["weblink"]
        filename, ext = self.get_filename_and_ext(file["name"])
        scrape_item.possible_datetime = file["mtime"]
        await self.handle_file(
            scrape_item.url, scrape_item, file["name"], ext, debrid_link=dl_link, custom_filename=filename
        )
