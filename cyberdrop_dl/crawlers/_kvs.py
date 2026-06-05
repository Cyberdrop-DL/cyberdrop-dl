"""Kernel Video Sharing, https://www.kernel-video-sharing.com"""

from __future__ import annotations

import dataclasses
import itertools
import re
from typing import TYPE_CHECKING, Any, ClassVar, final

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import DownloadError, ScrapeError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text, open_graph, parse_url

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Generator, Sequence

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem


@dataclasses.dataclass(slots=True)
class KVSVideo:
    id: str
    title: str
    url: AbsoluteHttpURL
    resolution: Resolution


class Selector:
    UNAUTHORIZED = "div.video-holder:-soup-contains('This video is a private video')"
    FLASHVARS = "script:-soup-contains('video_id:')"
    USER_NAME = "div.headline > h2"
    ALBUM_NAME = "div.headline > h1"
    ALBUM_PICTURES = "div.album-list > a, .images a"
    PICTURE = "div.photo-holder > img"
    PUBLIC_VIDEOS = "div#list_videos_public_videos_items"
    PRIVATE_VIDEOS = "div#list_videos_private_videos_items"
    FAVOURITE_VIDEOS = "div#list_videos_favourite_videos_items"
    COMMON_VIDEOS_TITLE = "div#list_videos_common_videos_list h1"
    VIDEOS = "div#list_videos_common_videos_list_items a"
    NEXT_PAGE = "li.pagination-next > a"
    ALBUM_ID = "script:-soup-contains('album_id')"


class KernelVideoSharingCrawler(Crawler, is_abc=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Albums": "/albums/<album_name>",
        "Image": "/albums/<album_name>/<image_name>",
        "Search": "/search/?q=<query>",
        "Categories": "/categories/<name>",
        "Tags": "/tags/<name>",
        "Videos": "/videos/<slug>",
        "Members": "/members/<member_id>",
    }
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    _RATE_LIMIT: ClassVar[RateLimit] = 6, 5

    def __init_subclass__(cls, *, ensure_trailing_slash: bool = False, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if ensure_trailing_slash:
            cls.transform_url = cls.transform_kvs_url
            cls.DEFAULT_TRIM_URLS = False

    @final
    @classmethod
    def transform_kvs_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        return cls.ensure_trailing_slash(super().transform_url(url))

    @final
    @classmethod
    def ensure_trailing_slash(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        if url.name:
            return url / ""
        return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:  # noqa: PLR0911
        match scrape_item.url.parts[1:]:
            case ["categories" | "tags", _]:
                return await self.collection(scrape_item)
            case ["search", query]:
                return await self.collection(scrape_item, query)
            case ["members", _, *_]:
                return await self.profile(scrape_item)
            case ["videos", _, *_]:
                return await self.video(scrape_item)
            case ["albums", _]:
                return await self.album(scrape_item)
            case ["albums", _, _, *_]:
                return await self.picture(scrape_item)
            case _:
                if query := scrape_item.url.query.get("q"):
                    return await self.collection(scrape_item, query)
                raise ValueError

    @classmethod
    def _clean_title(cls, title: str) -> str:
        if title.startswith("New Videos Tagged"):
            title = title.partition("Showing")[0].partition("Tagged with")[-1].strip()
        elif title.startswith(trash := "New Videos for: ") or title.startswith(trash := "Videos for: "):  # noqa: PIE810
            title = title.partition(trash)[-1]
        else:
            title = title.partition("New Videos")[0].strip()

        title, _, rest = title.rpartition(", Page")
        return title or rest

    @classmethod
    def _collection_title(cls, soup: BeautifulSoup) -> str:
        return cls._clean_title(css.select_text(soup, Selector.COMMON_VIDEOS_TITLE))

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, query: str | None = None) -> None:
        soup = await self.request_soup(scrape_item.url)
        if query:
            title = f"{query} [search]"
        else:
            common_title = css.select_text(soup, Selector.COMMON_VIDEOS_TITLE)
            if common_title.startswith("New Videos Tagged"):
                common_title = common_title.split("Showing")[0].split("Tagged with")[1].strip()
                title = f"{common_title} [tag]"
            else:
                common_title = common_title.split("New Videos")[0].strip()
                title = f"{common_title} [category]"

        title = self.create_title(title)
        scrape_item.setup_as_album(title)
        await self._iter_videos(scrape_item)

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        user_name: str = (
            css.select_text(soup, Selector.USER_NAME).split("'s Profile")[0].strip().removesuffix("'s Page")
        )
        title = self.create_title(f"{user_name} [user]")
        scrape_item.setup_as_profile(title)

        if soup.select_one(Selector.PUBLIC_VIDEOS):
            await self._iter_videos(scrape_item, "public_videos")
        if soup.select_one(Selector.FAVOURITE_VIDEOS):
            await self._iter_videos(scrape_item, "favourite_videos")
        if soup.select_one(Selector.PRIVATE_VIDEOS):
            await self._iter_videos(scrape_item, "private_videos")

    async def _iter_videos(self, scrape_item: ScrapeItem, video_category: str = "") -> None:
        url = scrape_item.url / video_category if video_category else scrape_item.url
        async for soup in self.web_pager(url):
            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.VIDEOS):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        video = extract_kvs_video(self, soup)
        filename, ext = self.get_filename_and_ext(video.url.name)

        try:
            date_str = css.json_ld(soup)["uploadDate"]
        except (LookupError, ValueError, css.SelectorError):
            # Human date parsing was removed from parse_date. This fallback
            # no longer supports relative strings like "2 hours ago".
            pass
        else:
            scrape_item.uploaded_at = self.parse_iso_date(date_str)

        await self.handle_file(
            scrape_item.url,
            scrape_item,
            filename,
            ext,
            custom_filename=self.create_custom_filename(
                video.title,
                ext,
                file_id=video.id,
                resolution=video.resolution,
            ),
            debrid_link=video.url,
        )

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str | None = None) -> None:
        soup = await self.request_soup(scrape_item.url)
        if not album_id:
            js_text = css.select_text(soup, Selector.ALBUM_ID)
            album_id = extr_text(js_text, "params['album_id'] =", ";")

        results = await self.get_album_results(album_id)
        title = css.select_text(soup, Selector.ALBUM_NAME)
        title = self.create_title(f"{title} [album]", album_id)
        scrape_item.setup_as_album(title, album_id=album_id)
        for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.ALBUM_PICTURES, results=results):
            self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def picture(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        src = self.parse_url(css.select(soup, Selector.PICTURE, "src"))
        await self.direct_file(scrape_item, src)

    async def _ajax_pagination(  # noqa: PLR0913
        self,
        url: AbsoluteHttpURL,
        block_id: str,
        *,
        last_page: int | None = None,
        mode: str = "async",
        function: str = "get_block",
        is_private: int = 0,
        sort_by: str = "",
        from_query_param_name: str = "from",
        q: str | None = None,
    ) -> AsyncIterator[BeautifulSoup]:
        page_url = url.with_query(
            mode=mode,
            function=function,
            block_id=block_id,
            is_private=is_private,
            sort_by=sort_by,
        )
        if q is not None:
            page_url = page_url.update_query(q=q)

        for page in itertools.count(2):
            if last_page is not None and page > last_page:
                break
            page_url = page_url.update_query({from_query_param_name: page})
            try:
                soup = await self.request_soup(page_url)
            except DownloadError as e:
                if e.status == 404:
                    break
                raise

            yield soup


def extract_kvs_video(cls: Crawler, soup: BeautifulSoup) -> KVSVideo:
    if soup.select_one(Selector.UNAUTHORIZED):
        raise ScrapeError(401, "Private video")

    script = css.select_text(soup, Selector.FLASHVARS)
    video = _parse_video_vars(script)
    if not video.title:
        title = open_graph.get_title(soup) or css.page_title(soup)
        assert title
        video.title = css.rstrip_domain(title, cls.DOMAIN)
    return video


# URL de-obfuscation code for kvs, adapted from yt-dlp
# https://github.com/yt-dlp/yt-dlp/blob/e1847535e28788414a25546a45bebcada2f34558/yt_dlp/extractor/generic.py


_HASH_LENGTH = 32
_match_video_url_keys = re.compile(r"^video_(?:url|alt_url\d*)$").match
_find_flashvars = re.compile(r"(\w+):\s*'([^']*)'").findall


def _parse_video_vars(video_vars: str) -> KVSVideo:
    flashvars: dict[str, str] = dict(_find_flashvars(video_vars))
    resolution, url = max(_parse_formats(flashvars))
    return KVSVideo(
        flashvars["video_id"],
        flashvars.get("video_title", ""),
        url,
        resolution,
    )


def _parse_formats(flashvars: dict[str, str]) -> Generator[tuple[Resolution, AbsoluteHttpURL]]:
    url_keys = list(filter(_match_video_url_keys, flashvars.keys()))
    license_token = _get_license_token(flashvars["license_code"])
    parse_resolution = Resolution.make_parser()
    for key in url_keys:
        url_str = flashvars[key]
        if "/get_file/" not in url_str:
            continue
        quality = flashvars.get(f"{key}_text")
        resolution = Resolution.highest() if quality in {"HQ", "Best Quality"} else parse_resolution(quality)
        url = _deobfuscate_url(url_str, license_token)
        yield resolution, url


def _get_license_token(license_code: str) -> tuple[int, ...]:
    license_code = license_code.removeprefix("$")
    license_values = [int(char) for char in license_code]
    modlicense = license_code.replace("0", "1")
    middle = len(modlicense) // 2
    fronthalf = int(modlicense[: middle + 1])
    backhalf = int(modlicense[middle:])
    modlicense = str(4 * abs(fronthalf - backhalf))[: middle + 1]

    return tuple(
        (license_values[index + offset] + current) % 10
        for index, current in enumerate(map(int, modlicense))
        for offset in range(4)
    )


def _deobfuscate_url(video_url_str: str, license_token: Sequence[int]) -> AbsoluteHttpURL:
    raw_url_str = video_url_str.removeprefix("function/0/")
    url = parse_url(raw_url_str)
    is_obfuscated = raw_url_str != video_url_str
    if not is_obfuscated:
        return url

    checksum, tail = url.parts[3][:_HASH_LENGTH], url.parts[3][_HASH_LENGTH:]
    indices = list(range(_HASH_LENGTH))

    # Swap indices of hash according to the destination calculated from the license token
    accum = 0
    for src in reversed(range(_HASH_LENGTH)):
        accum += license_token[src]
        dest = (src + accum) % _HASH_LENGTH
        indices[src], indices[dest] = indices[dest], indices[src]

    new_parts = list(url.parts)
    new_parts[3] = "".join(checksum[index] for index in indices) + tail
    return url.with_path("/".join(new_parts[1:]), keep_query=True, keep_fragment=True)
