# https://owncloud.dev/apis/http/webdav/#calling-the-webdav-api

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.utils import webdav
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem


class OwnCloudCrawler(Crawler, is_generic=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Public Share": ("/s/<share_token>")}
    DEFAULT_TRIM_URLS: ClassVar[bool] = False

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["s", folder_token]:
                return await self.public_share(scrape_item, folder_token)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def public_share(self, scrape_item: ScrapeItem, share_token: str) -> None:
        origin = scrape_item.url.origin()
        webdav_url = origin / "public.php/dav/files" / share_token

        for resource in await self.request_webdav(webdav_url):
            if resource.is_collection:
                continue

            url = self.parse_url(resource.href, origin)
            new_item = scrape_item.create_child(url)
            await self._file(new_item, resource)
            scrape_item.add_children()

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: webdav.Resource) -> None:
        filename, ext = self.get_filename_and_ext(file.name, mime_type=file.content_type)
        scrape_item.upload_date = file.last_modified
        await self.handle_file(scrape_item.url, scrape_item, filename, ext)

    async def request_webdav(self, url: AbsoluteHttpURL) -> tuple[webdav.Resource, ...]:
        content = await self.request_text(
            url,
            method=webdav.Method.PROPFIND,  # pyright: ignore[reportArgumentType]
            headers={
                "Depth": "infinity",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": str(url.origin()),
                "Content-Type": "text/plain;charset=UTF-8",
            },
            data=webdav.DEFAULT_PROPFIND,
        )

        return tuple(webdav.parse_propfind(content))
