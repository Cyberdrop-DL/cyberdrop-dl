from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper

from .xenforo import XenforoCrawler

if TYPE_CHECKING:
    import yarl

_confirmation_data = ({"xhr": "1", "download": "1"},)


class F95ZoneCrawler(XenforoCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://f95zone.to")
    DOMAIN: ClassVar[str] = "f95zone"
    FOLDER_DOMAIN: ClassVar[str] = "F95Zone"

    @error_handling_wrapper
    async def resolve_confirmation_link(self, link: AbsoluteHttpURL) -> AbsoluteHttpURL | None:
        json_resp = await self.request_json(link, method="POST", data=_confirmation_data)
        if json_resp["status"] == "ok":
            return self.parse_url(json_resp["msg"])

    @classmethod
    def is_thumbnail(cls, link: AbsoluteHttpURL) -> bool:
        return "thumb" in link.parts

    @classmethod
    def thumbnail_to_img(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        return url.with_path(url.path.replace("/thumb/", ""))

    @classmethod
    def parse_url(
        cls,
        url: yarl.URL | str,
        /,
        relative_to: AbsoluteHttpURL | None = None,
        *,
        trim: bool | None = None,
    ) -> AbsoluteHttpURL:
        url = super().parse_url(url, relative_to, trim=trim)
        if cls.is_thumbnail(url):
            return cls.thumbnail_to_img(url)
        return url
