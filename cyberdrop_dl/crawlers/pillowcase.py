from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class PillowCaseCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": (
            "/f/<file_uid>",
            "/api/download/<file_uid>",
            "/api/get/<file_uid>",
            "/api/metadata/<file_uid>.txt",
        ),
    }
    DOMAIN: ClassVar[str] = "pillowcase"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("pillowcase.su",)
    FOLDER_DOMAIN: ClassVar[str] = "PillowCase"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pillows.su")

    def __post_init__(self) -> None:
        self.api: PillowCaseAPI = PillowCaseAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["f", file_id]:
                return await self.file(scrape_item, file_id)
            case ["api", "download" | "get" | "metadata", slug, *_]:
                return await self.file(scrape_item, file_id=slug.partition(".")[0])
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        name, src = await self.api.download(file_id)
        _, ext = self.get_filename_and_ext(name)
        filename = self.create_custom_filename(name, ext, file_id=file_id)
        if self.config.dump_json:
            metadata = await self.api.metadata(file_id)
            metadata = f"FILENAME: {name}\n\n{metadata}"
            self.create_eager_task(self.write_metadata(scrape_item, file_id, metadata))

        await self.handle_file(src, scrape_item, name, ext, custom_filename=filename)


class PillowCaseAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.pillows.su/api")

    async def download(self, file_id: str) -> tuple[str, AbsoluteHttpURL]:
        url = self.ENTRYPOINT / "download" / file_id
        async with self.request(url, "HEAD") as resp:
            return resp.content_disposition.filename, url

    async def metadata(self, file_id: str) -> str:
        url = self.ENTRYPOINT / "metadata" / f"{file_id}.txt"
        return await self.request_text(url)
