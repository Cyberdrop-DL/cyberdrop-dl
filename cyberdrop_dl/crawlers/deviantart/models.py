from __future__ import annotations

from typing import Any, TypedDict

from cyberdrop_dl.models import DeferredModel


class CachedToken(TypedDict):
    access_token: str
    refresh_token: str
    expires_at: float
    seed_hash: str


class OAuthTokenResponse(DeferredModel):
    access_token: str
    token_type: str = "Bearer"  # noqa: S105
    expires_in: int = 3600
    refresh_token: str | None = None
    scope: str | None = None
    status: str = "success"


class Author(DeferredModel):
    userid: str
    username: str
    usericon: str = ""
    type: str = ""


class MediaContent(DeferredModel):
    src: str
    height: int = 0
    width: int = 0
    transparency: bool = False
    filesize: int = 0


class MediaThumb(DeferredModel):
    src: str
    height: int = 0
    width: int = 0
    transparency: bool = False


class DeviationVideo(DeferredModel):
    src: str
    quality: str = ""
    filesize: int = 0
    duration: float = 0.0

    @property
    def quality_score(self) -> tuple[int, int]:
        quality = self.quality.casefold()
        if "orig" in quality:
            return (100_000, self.filesize)

        digits = "".join(ch for ch in quality if ch.isdigit())
        height = int(digits) if digits else 0
        return (height, self.filesize)


class FlashMedia(DeferredModel):
    src: str
    height: int = 0
    width: int = 0


class TextContent(DeferredModel):
    excerpt: str = ""
    body: dict[str, Any] | None = None


class Deviation(DeferredModel):
    deviationid: str
    url: str = ""
    title: str = ""
    published_time: int | str | None = None
    is_deleted: bool = False
    is_mature: bool = False
    is_downloadable: bool = False
    download_filesize: int = 0
    allows_comments: bool = True
    author: Author | None = None
    content: MediaContent | None = None
    preview: MediaContent | None = None
    thumbs: tuple[MediaThumb, ...] = ()
    videos: tuple[DeviationVideo, ...] = ()
    flash: FlashMedia | None = None
    excerpt: str | None = None
    text_content: TextContent | None = None

    @property
    def published_timestamp(self) -> int | None:
        if self.published_time is None or self.published_time == "":
            return None
        try:
            return int(self.published_time)
        except ValueError:
            return None


class DownloadResponse(DeferredModel):
    src: str
    filename: str = ""
    width: int = 0
    height: int = 0
    filesize: int = 0


class DeviationContent(DeferredModel):
    html: str = ""
    css: str = ""
    css_fonts: tuple[str, ...] = ()


class Folder(DeferredModel):
    folderid: str
    parent: str | None = None
    name: str = ""
    size: int = 0
    has_subfolders: bool = False


class FolderPage(DeferredModel):
    has_more: bool = False
    next_offset: int | None = None
    results: tuple[Folder, ...] = ()


class DeviationListPage(DeferredModel):
    has_more: bool = False
    next_offset: int | None = None
    name: str | None = None
    results: tuple[Deviation, ...] = ()
