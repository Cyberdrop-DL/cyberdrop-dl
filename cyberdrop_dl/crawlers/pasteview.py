from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedDomains, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem
from cyberdrop_dl.utils import error_handling_wrapper, get_download_path

if TYPE_CHECKING:
    from pathlib import Path

    from cyberdrop_dl.url_objects import ScrapeItem


PRIMARY_URL = AbsoluteHttpURL("https://pasteview.com")
_API_PASTES = PRIMARY_URL / "api/pastes"
_API_PASTES_DATA = PRIMARY_URL / "api/pastesData"


class PasteMetadata(BaseModel):
    message: str
    result: dict[str, Any]


class PasteData(BaseModel):
    message: str
    result: dict[str, Any]


class PasteViewCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "pasteview.com"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Paste": "/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "pasteview"
    FOLDER_DOMAIN: ClassVar[str] = "PasteView"
    _RATE_LIMIT: ClassVar[RateLimit] = 1, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        paste_id = scrape_item.url.parts[1]
        if not paste_id or len(paste_id) < 5:
            raise ValueError

        await self.paste(scrape_item, paste_id)

    @error_handling_wrapper
    async def paste(self, scrape_item: ScrapeItem, paste_id: str) -> None:
        metadata_url = _API_PASTES / paste_id / "false"
        metadata_resp: PasteMetadata = await self.request_json(metadata_url)

        if metadata_resp.message != "Paste metadata found successfully":
            raise ScrapeError(404, "Paste not found")

        field_id = metadata_resp.result.get("fieldId", "")

        data_url = _API_PASTES_DATA / field_id / "0"
        data_resp: PasteData = await self.request_json(
            data_url,
            params={"pasteId": paste_id, "password": ""},
        )

        if data_resp.message != "Paste data found successfully":
            raise ScrapeError(404, "Paste content not found")

        content = data_resp.result.get("data", "")
        filename = self._extract_filename(content, paste_id)

        download_folder = get_download_path(self.manager, scrape_item, self.FOLDER_DOMAIN)
        file_path = download_folder / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        await aio.write_bytes(file_path, content.encode("utf-8"))

        url = AbsoluteHttpURL(scrape_item.url.with_scheme("text"))
        media_item = MediaItem.from_item(
            scrape_item,
            url,
            self.DOMAIN,
            db_path="",
            download_folder=download_folder,
            filename=filename,
        )
        if self.manager.config.settings.files.dump_json:
            await self.manager.logs.write_jsonl([media_item.serialize()])

        self.manager.scrape_mapper.tui.files.stats.completed += 1

    def _extract_filename(self, content: str, paste_id: str) -> str:
        first_line = content.split("\n")[0].strip()

        if first_line and len(first_line) < 100 and not first_line.startswith("#"):
            filename = (
                first_line.replace("/", "_")
                .replace("\\", "_")
                .replace(":", "_")
                .replace("<", "_")
                .replace(">", "_")
                .replace('"', "_")
                .replace("*", "_")
                .replace("?", "_")
                .replace("|", "_")
            )
            if filename and "." not in filename.split("/")[-1]:
                filename += ".txt"
            if filename:
                return filename

        return f"{paste_id}.txt"
