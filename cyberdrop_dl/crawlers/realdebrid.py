"""https://api.real-debrid.com"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.cache import disk_cached_method
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.crawler import API, Crawler, auto_task_id
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils._url import is_within_domain
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem

_ERROR_CODES = MappingProxyType(
    {
        -1: "Internal error",
        1: "Missing parameter",
        2: "Bad parameter value",
        3: "Unknown method",
        4: "Method not allowed",
        5: "Slow down",
        6: "Resource unreachable",
        7: "Resource not found",
        8: "Bad token",
        9: "Permission denied",
        10: "Two-Factor authentication needed",
        11: "Two-Factor authentication pending",
        12: "Invalid login",
        13: "Invalid password",
        14: "Account locked",
        15: "Account not activated",
        16: "Unsupported hoster",
        17: "Hoster in maintenance",
        18: "Hoster limit reached",
        19: "Hoster temporarily unavailable",
        20: "Hoster not available for free users",
        21: "Too many active downloads",
        22: "IP Address not allowed",
        23: "Traffic exhausted",
        24: "File unavailable",
        25: "Service unavailable",
        26: "Upload too big",
        27: "Upload error",
        28: "File not allowed",
        29: "Torrent too big",
        30: "Torrent file invalid",
        31: "Action already done",
        32: "Image resolution error",
        33: "Torrent already active",
        34: "Too many requests",
        35: "Infringing file",
        36: "Fair Usage Limit",
    }
)


def _check_json(resp: Any, _: Any = None) -> None:
    if type(resp) is dict and (code := resp.get("error_code")):
        code = 7 if code == 16 else code
        msg = _ERROR_CODES.get(code, "Unknown error").capitalize()
        ui_failure = f"RealDebrid Error ({code})"
        raise ScrapeError(ui_failure, msg)


class RealDebridCrawler(Crawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://real-debrid.com")
    DOMAIN: ClassVar[str] = "real-debrid"
    FOLDER_DOMAIN: ClassVar[str] = "RealDebrid"

    def __post_init__(self) -> None:
        token = self.config.auth.real_debrid.api_key
        self.disabled: bool = not token
        self.api: RealDebridAPI = RealDebridAPI.from_crawler(self)
        self.api.token = token

    async def __async_post_init__(self) -> None:
        if self.disabled:
            return

        async with (
            self.catch_errors(self.api.ENTRYPOINT),
            self.disable_on_error("Setup failed. Unable to get suppoerted domains"),
        ):
            await self.api.connect()

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        url = scrape_item.url
        if URLParser.is_unrestricted_download(url):
            await self.direct_file(scrape_item)
        elif "real-debrid" in url.host:
            raise ValueError
        elif folder := URLParser.guess_folder_id(url):
            await self.folder(scrape_item, folder)
        else:
            await self.file(scrape_item)

    @error_handling_wrapper
    async def folder(self, scrape_item: ScrapeItem, folder_id: str) -> None:
        title = self.create_title(f"{folder_id} [{scrape_item.url.host}]", folder_id)
        scrape_item.setup_as_album(title, album_id=folder_id)
        links: list[str] = await self.api.unrestrict_folder(scrape_item.url)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            for url in map(self.parse_url, links):
                tg.create_task(self._file_task(scrape_item.create_child(url)))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        url = scrape_item.url
        if await self.check_complete_from_referer(scrape_item.url):
            return

        scrape_item.setup_as_album(self.create_title(f"files [{url.host}]"))
        dl_url, name = await self.api.unrestrict(url, scrape_item.password)
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(
            url,
            scrape_item,
            name,
            ext,
            debrid_link=dl_url,
            custom_filename=filename,
        )

    _file_task = auto_task_id(file)


@HTTPConfig(rate_limit=(250, 60), json_check=_check_json, headers={"Referer": CDL_USER_AGENT})
class RealDebridAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.real-debrid.com/rest/1.0")
    token: str | None
    _domains: set[str]

    def is_supported_domain(self, url: AbsoluteHttpURL) -> bool:
        return bool(
            url.host in self._domains
            or (self._domains and any(is_within_domain(domain, url.host) for domain in self._domains))
        )

    async def connect(self) -> None:
        self._domains = set(await self.domains())

    @disk_cached_method(ttl=86400 * 5)
    async def get_hosts_regexes(self) -> dict[str, list[str]]:
        file_regex, folder_regex = await aio.gather(
            self._request("hosts/regex"),
            self._request("hosts/regexFolder"),
            fail_fast=False,
        )
        return {"regex": file_regex, "regexFolder": folder_regex}

    @disk_cached_method(ttl=86400 * 5)
    async def domains(self) -> tuple[str, ...]:
        return tuple(await self._request("hosts/domains"))

    async def unrestrict(self, url: AbsoluteHttpURL, password: str | None) -> tuple[AbsoluteHttpURL, str]:
        resp: dict[str, Any] = await self._request("unrestrict/link", link=url, password=password, remote=False)
        dl_url = self.parse_url(resp["download"])
        self.log.info("\n  Original URL: %s\n  Debrid URL: %s", url, dl_url)
        return dl_url, resp.get("filename") or dl_url.name

    async def unrestrict_folder(self, url: AbsoluteHttpURL) -> list[str]:
        return await self._request("unrestrict/folder", url)

    async def _request(self, path: str, /, link: AbsoluteHttpURL | None = None, **data: Any) -> Any:
        if link:
            data["link"] = str(link)

        return await self.request_json(
            self.ENTRYPOINT / path,
            "POST" if data else "GET",
            headers={"Authorization": f"Bearer {self.token}"},
            data=data or None,
        )


# TODO: delete this entire class in v9. Save URLs in the database as is. Move this logic to a transfer module
class URLParser:
    _DB_FLATTEN_URL_KEYS = "parts", "query", "frag"

    @classmethod
    def guess_folder_id(cls, url: AbsoluteHttpURL) -> str | None:
        for word in ("folder", "folders", "dir"):
            try:
                return url.parts[url.parts.index(word) + 1]
            except (IndexError, ValueError):
                continue

        for word in ("sharekey",):
            if folder := url.query.get(word):
                return folder

    @classmethod
    def is_unrestricted_download(cls, url: AbsoluteHttpURL) -> bool:
        return any(p in url.host for p in ("download.", "my.")) and "real-debrid" in url.host

    @classmethod
    def reconstruct_original_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        """Reconstructs an URL that might have been flatten for the database."""
        if (
            len(url.parts) < 3
            or url.host != RealDebridCrawler.PRIMARY_URL.host
            or url.parts[1].count(".") == 0
            or cls.is_unrestricted_download(url)
        ):
            return url

        parts_dict: dict[str, tuple[str, ...]] = dict.fromkeys(cls._DB_FLATTEN_URL_KEYS, ())
        key = "parts"
        original_host = url.parts[1]
        for part in url.parts[2:]:
            if part in cls._DB_FLATTEN_URL_KEYS[1:]:
                key = part
                continue
            parts_dict[key] += (part,)

        path = "/".join(parts_dict["parts"])
        parsed_url = AbsoluteHttpURL(f"https://{original_host}/{path}", encoded="%" in path)
        query_iter = iter(parts_dict["query"])
        if query := tuple(zip(query_iter, query_iter, strict=True)):
            parsed_url = parsed_url.with_query(query)
        if frag := next(iter(parts_dict["frag"]), None):
            parsed_url = parsed_url.with_fragment(frag)

        return parsed_url

    @classmethod
    def flatten_url(cls, original_url: AbsoluteHttpURL, host: str) -> AbsoluteHttpURL:
        """Some hosts use query params or fragment as id or password (ex: mega.nz)
        This function flattens the query and fragment as parts of the URL path because database lookups only use the url path"""
        flatten_url = RealDebridCrawler.PRIMARY_URL / host / original_url.path[1:]
        if original_url.query:
            query_params = (item for pair in original_url.query.items() for item in pair)
            flatten_url = flatten_url / "query" / "/".join(query_params)

        if original_url.fragment:
            flatten_url = flatten_url / "frag" / original_url.fragment

        return flatten_url
