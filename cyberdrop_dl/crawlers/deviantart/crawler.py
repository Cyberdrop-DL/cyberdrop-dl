from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths, URLConfig, auto_task_id
from cyberdrop_dl.crawlers.deviantart.api import DeviantArtAPI
from cyberdrop_dl.exceptions import DownloadError, NoExtensionError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import is_within_domain, name_from_url

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterable, Callable

    from cyberdrop_dl.crawlers.deviantart.models import Deviation, DeviationListPage, Folder, FolderPage
    from cyberdrop_dl.filepath import Filename
    from cyberdrop_dl.url_objects import ScrapeItem


_UUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_UUID_RE = re.compile(rf"^{_UUID_PATTERN}$", re.IGNORECASE)
_APP_URL_UUID_RE = re.compile(rf"DeviantArt://deviation/({_UUID_PATTERN})", re.IGNORECASE)
_JSON_DEVIATION_UUID_RE = re.compile(rf'"deviationId"\s*:\s*"({_UUID_PATTERN})"', re.IGNORECASE)
_JSON_FOLDER_UUID_RE = re.compile(rf'"folder(?:Id|id)"\s*:\s*"({_UUID_PATTERN})"', re.IGNORECASE)
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")

_RESERVED_PATHS = frozenset(
    {
        "about",
        "account",
        "api",
        "art",
        "core-membership",
        "daily-deviations",
        "deviation",
        "favourites",
        "favorites",
        "gallery",
        "join",
        "notifications",
        "oauth2",
        "search",
        "settings",
        "tag",
        "users",
        "watch",
    }
)


def _is_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value))


def _slugify(value: str) -> str:
    return _SLUG_STRIP_RE.sub("-", value.casefold()).strip("-")


def _extract_deviation_uuid_from_slug(slug: str) -> str | None:
    if _is_uuid(slug):
        return slug
    if len(slug) > 36 and slug[-37] == "-" and _is_uuid(candidate := slug[-36:]):
        return candidate
    return None


def _resolve_section_route(section: str, username: str, rest: list[str]) -> tuple[str, tuple[str, ...]]:
    match rest:
        case [] | ["all"]:
            return ("gallery" if section == "gallery" else "favourites", (username,))
        case ["scraps"] if section == "gallery":
            return ("scraps", (username,))
        case [folder_id] | [folder_id, _] if not (section == "gallery" and folder_id == "scraps"):
            slug = rest[1] if len(rest) == 2 else ""
            route = "gallery_folder" if section == "gallery" else "collection_folder"
            return (route, (username, folder_id, slug))
        case _:
            raise ValueError


def _resolve_route(url: AbsoluteHttpURL) -> tuple[str, tuple[str, ...]]:
    parts = url.parts[1:]
    if not parts or not all(parts):
        raise ValueError

    if is_within_domain("fav.me", url.host):
        if len(parts) != 1:
            raise ValueError
        return ("fav_me", ())

    match parts:
        case ["deviation", deviation_id] if _is_uuid(deviation_id):
            return ("deviation", ("", deviation_id))
        case [username, "art", slug]:
            return ("deviation", (username, slug))
        case [username] if username.casefold() not in _RESERVED_PATHS:
            return ("gallery", (username,))
        case [username, ("gallery" | "favourites") as section, *rest]:
            return _resolve_section_route(section, username, rest)
        case _:
            raise ValueError


@URLConfig(strict_host_match=True)
@Crawler.db_path_builder("path")
class DeviantArtCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Deviation": "/<username>/art/<slug>-<id>",
        "Gallery": (
            "/<username>",
            "/<username>/gallery",
            "/<username>/gallery/all",
            "/<username>/gallery/scraps",
            "/<username>/gallery/<folder_id>/<slug>",
        ),
        "Favourites": (
            "/<username>/favourites",
            "/<username>/favourites/all",
            "/<username>/favourites/<folder_id>/<slug>",
        ),
        "Short link": "fav.me/<short_id>",
    }
    DOMAIN: ClassVar[str] = "deviantart"
    FOLDER_DOMAIN: ClassVar[str] = "DeviantArt"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.deviantart.com")
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ("deviantart.com", "fav.me")

    def __post_init__(self) -> None:
        self.api: DeviantArtAPI = DeviantArtAPI.from_crawler(self)

    @override
    async def __async_post_init__(self) -> None:
        async with (
            self.catch_errors(self.api.OAUTH_URL),
            self.disable_on_error("Unable to authenticate with DeviantArt"),
        ):
            await self.api.ensure_token()

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match _resolve_route(scrape_item.url):
            case ("fav_me", ()):
                await self.fav_me(scrape_item)
            case ("deviation", (username, slug)):
                await self.deviation(scrape_item, username, slug)
            case ("gallery", (username,)):
                await self.gallery(scrape_item, username)
            case ("scraps", (username,)):
                await self.scraps(scrape_item, username)
            case ("gallery_folder", (username, folder_id, slug)):
                await self.gallery_folder(scrape_item, username, folder_id, slug)
            case ("favourites", (username,)):
                await self.favourites(scrape_item, username)
            case ("collection_folder", (username, folder_id, slug)):
                await self.collection_folder(scrape_item, username, folder_id, slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def fav_me(self, scrape_item: ScrapeItem) -> None:
        redirect = await self.request_redirect(scrape_item.url)
        if scrape_item.url == redirect:
            raise ScrapeError(422, "Infinite redirect")
        if not is_within_domain("deviantart.com", redirect.host):
            raise ScrapeError(422, f"Unexpected redirect destination: {redirect.host}")
        scrape_item.url = redirect
        self.create_task(self.run(scrape_item))

    @error_handling_wrapper
    async def deviation(self, scrape_item: ScrapeItem, username: str, slug: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        deviation_id = await self._resolve_deviation_id(scrape_item.url, username, slug)
        deviation = await self.api.deviation(deviation_id)
        if deviation.url:
            scrape_item.url = self.parse_url(deviation.url)
        await self._handle_deviation(scrape_item, deviation)

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, username: str) -> None:
        scrape_item.setup_as_profile(self.create_title(username))
        seen_ids: set[str] = set()
        await self._iter_deviations(scrape_item, self.api.gallery_all(username), seen_ids=seen_ids)

        if self.config.crawlers.deviantart.include_scraps and (
            scraps_folder := await self._find_folder_by_name(self.api.gallery_folders(username), "scraps")
        ):
            scraps_item = scrape_item.create_new(self.PRIMARY_URL / username / "gallery/scraps")
            scraps_item.append_folders("Scraps")
            await self._iter_deviations(
                scraps_item,
                self.api.gallery_folder(username, scraps_folder.folderid),
                seen_ids=seen_ids,
            )

    @error_handling_wrapper
    async def scraps(self, scrape_item: ScrapeItem, username: str) -> None:
        folder = await self._find_folder_by_name(self.api.gallery_folders(username), "scraps")
        if not folder:
            raise ScrapeError(404, f"Scraps folder not found for {username}")

        scrape_item.setup_as_album(
            self.create_title(f"{username} - {folder.name}", folder.folderid), album_id=folder.folderid
        )
        await self._iter_deviations(scrape_item, self.api.gallery_folder(username, folder.folderid))

    @error_handling_wrapper
    async def gallery_folder(
        self,
        scrape_item: ScrapeItem,
        username: str,
        folder_id: str,
        slug: str = "",
    ) -> None:
        folder_uuid, folder_name = await self._resolve_folder(
            scrape_item.url,
            self.api.gallery_folders(username),
            folder_id,
            slug,
        )
        first_page, pages = await aio.peek_next(self.api.gallery_folder(username, folder_uuid))
        title_name = first_page.name or folder_name or folder_uuid
        scrape_item.setup_as_album(self.create_title(f"{username} - {title_name}", folder_uuid), album_id=folder_uuid)
        await self._iter_deviations(scrape_item, pages)

    @error_handling_wrapper
    async def favourites(self, scrape_item: ScrapeItem, username: str) -> None:
        scrape_item.setup_as_profile(self.create_title(f"{username} - Favourites"))
        await self._iter_deviations(scrape_item, self.api.collections_all(username))

    @error_handling_wrapper
    async def collection_folder(
        self,
        scrape_item: ScrapeItem,
        username: str,
        folder_id: str,
        slug: str = "",
    ) -> None:
        folder_uuid, folder_name = await self._resolve_folder(
            scrape_item.url,
            self.api.collection_folders(username),
            folder_id,
            slug,
        )
        first_page, pages = await aio.peek_next(self.api.collection_folder(username, folder_uuid))
        title_name = first_page.name or folder_name or folder_uuid
        scrape_item.setup_as_album(self.create_title(f"{username} - {title_name}", folder_uuid), album_id=folder_uuid)
        await self._iter_deviations(scrape_item, pages)

    async def _iter_deviations(
        self,
        scrape_item: ScrapeItem,
        pages: AsyncIterable[DeviationListPage],
        *,
        seen_ids: set[str] | None = None,
    ) -> None:
        seen = seen_ids if seen_ids is not None else set()
        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg, aio.maybe_aclosing(pages):
            async for page in pages:
                for deviation in page.results:
                    if deviation.deviationid in seen:
                        continue
                    seen.add(deviation.deviationid)
                    web_url = (
                        self.parse_url(deviation.url)
                        if deviation.url
                        else self.PRIMARY_URL / "deviation" / deviation.deviationid
                    )
                    new_item = scrape_item.create_child(web_url)
                    tg.create_task(self._deviation_task(new_item, deviation))
                    scrape_item.add_children()
                    await sleep()

    @error_handling_wrapper
    async def _handle_deviation(self, scrape_item: ScrapeItem, deviation: Deviation) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        if deviation.is_deleted:
            raise ScrapeError(410, f"Deviation {deviation.deviationid} has been deleted")

        if deviation.is_mature and not self.config.crawlers.deviantart.include_mature:
            self.log.info("Skipping mature deviation %s due to config [include_mature=false]", deviation.deviationid)
            self.tui.files.stats.skipped += 1
            return

        scrape_item.uploaded_at = deviation.published_timestamp
        if post_title := self.create_separate_post_title(
            deviation.title or None,
            deviation.deviationid,
            deviation.published_timestamp,
        ):
            scrape_item.append_folders(post_title)

        src, orig_name = await self._select_media(deviation)
        if src is None:
            if deviation.excerpt is not None or deviation.text_content is not None:
                content = await self.api.deviation_content(deviation.deviationid)
                payload = deviation.model_dump(mode="json") | {"text_html": content.model_dump(mode="json")}
                await self.write_metadata(scrape_item, f"deviation_{deviation.deviationid}", payload)
                return
            raise ScrapeError(422, f"No downloadable media found for deviation {deviation.deviationid}")

        filename = await self._resolve_filename_and_ext(src, orig_name)
        title = deviation.title or deviation.deviationid
        custom_filename = self.create_custom_filename(title, filename.suffix, file_id=deviation.deviationid)
        thumb = self.parse_url(deviation.thumbs[-1].src) if deviation.thumbs else None

        await self.handle_file(
            src,
            scrape_item,
            orig_name or src.name,
            filename.suffix,
            custom_filename=custom_filename,
            thumbnail=thumb,
            metadata=deviation,
        )

    _deviation_task = auto_task_id(_handle_deviation)

    async def _select_media(self, deviation: Deviation) -> tuple[AbsoluteHttpURL | None, str]:
        if self.config.crawlers.deviantart.download_originals and deviation.is_downloadable:
            try:
                dl = await self.api.download_deviation(deviation.deviationid)
            except (DownloadError, ScrapeError) as e:
                self.log.warning(
                    "Original download endpoint failed for %s (%s), falling back to preview/content media",
                    deviation.deviationid,
                    e,
                )
            else:
                if dl.src:
                    src = self.parse_url(dl.src)
                    return src, dl.filename or name_from_url(src)

        if deviation.videos:
            best_video = max(deviation.videos, key=lambda v: v.quality_score)
            src = self.parse_url(best_video.src)
            return src, name_from_url(src)

        if deviation.content and deviation.content.src:
            src = self.parse_url(deviation.content.src)
            return src, name_from_url(src)

        if deviation.flash and deviation.flash.src:
            src = self.parse_url(deviation.flash.src)
            return src, name_from_url(src)

        if deviation.preview and deviation.preview.src:
            src = self.parse_url(deviation.preview.src)
            return src, name_from_url(src)

        return None, ""

    async def _resolve_filename_and_ext(self, src: AbsoluteHttpURL, orig_name: str) -> Filename:
        candidate = orig_name or name_from_url(src)
        try:
            return self.get_filename_and_ext(candidate, assume_ext=None)
        except NoExtensionError:
            ext = src.suffix or await self.sniff_ext(src)
            stem = candidate or "file"
            return self.get_filename_and_ext(f"{stem}{ext}")

    async def _resolve_deviation_id(self, url: AbsoluteHttpURL, username: str, slug: str) -> str:
        if uuid := _extract_deviation_uuid_from_slug(slug):
            return uuid

        try:
            html = await self.request_text(url)
        except (DownloadError, ScrapeError):
            html = ""

        if html:
            for pattern in (_APP_URL_UUID_RE, _JSON_DEVIATION_UUID_RE):
                if match := pattern.search(html):
                    return match.group(1)

        _, _, legacy_id = slug.rpartition("-")
        if legacy_id.isdigit():
            suffix = f"-{legacy_id}"
            async with aio.maybe_aclosing(self.api.gallery_all(username)) as pages:
                async for page in pages:
                    for item in page.results:
                        if item.url.rstrip("/").endswith(suffix):
                            return item.deviationid

        raise ScrapeError(404, f"Unable to resolve DeviantArt deviation ID for {url}")

    async def _find_folder(
        self,
        folder_pages: AsyncGenerator[FolderPage],
        predicate: Callable[[Folder], bool],
    ) -> Folder | None:
        async with aio.maybe_aclosing(folder_pages):
            async for page in folder_pages:
                for folder in page.results:
                    if predicate(folder):
                        return folder
        return None

    async def _find_folder_by_name(self, folder_pages: AsyncGenerator[FolderPage], name: str) -> Folder | None:
        target = name.casefold()
        return await self._find_folder(folder_pages, lambda f: f.name.casefold() == target)

    async def _resolve_folder(
        self,
        url: AbsoluteHttpURL,
        folder_pages: AsyncGenerator[FolderPage],
        folder_id: str,
        slug: str,
    ) -> tuple[str, str]:
        if _is_uuid(folder_id):
            return folder_id, slug.replace("-", " ")

        slug_norm = _slugify(slug)
        matched_folder: Folder | None = None
        async with aio.maybe_aclosing(folder_pages):
            async for page in folder_pages:
                for folder in page.results:
                    if folder.folderid == folder_id:
                        return folder.folderid, folder.name
                    if slug_norm and _slugify(folder.name) == slug_norm and matched_folder is None:
                        matched_folder = folder

        if matched_folder is not None:
            return matched_folder.folderid, matched_folder.name

        try:
            html = await self.request_text(url)
        except (DownloadError, ScrapeError):
            html = ""

        if html and (match := _JSON_FOLDER_UUID_RE.search(html)):
            return match.group(1), slug.replace("-", " ")

        raise ScrapeError(404, f"Unable to resolve DeviantArt folder ID for {url}")
