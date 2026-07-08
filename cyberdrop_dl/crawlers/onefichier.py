from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedDomains, SupportedPaths
from cyberdrop_dl.exceptions import PasswordProtectedError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    NO_FREE_DOWNLOAD = ".ct_warn:-soup-contains('Free download is temporarily limited due to high demand')"
    RATE_LIMITED = ".ct_warn:-soup-contains('You must wait')"
    DL_LINK = "a:-soup-contains-own('Start your download')"
    FILENAME = "table td.normal span[style='font-weight:bold']"
    PREMIUM_REQUIRED = (
        ".ct_warn:-soup-contains('The owner of this file has reserved access to the subscribers of our services')"
    )


class OneFichierCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "1fichier.com",
        "alterupload.com",
        "cjoint.net",
        "desfichiers.com",
        "dfichiers.com",
        "megadl.fr",
        "mesfichiers.org",
        "piecejointe.net",
        "pjointe.com",
        "tenvoi.com",
        "dl4free.com",
    )  # https://1fichier.com/api.html
    RATE_LIMIT: ClassVar[RateLimit] = 1, 2
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": "?<file_id>",
    }
    ALLOW_EMPTY_PATH: ClassVar[bool] = True
    DOMAIN: ClassVar[str] = "1fichier"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://1fichier.com")
    _DOWNLOAD_SLOTS: ClassVar[int | None] = 1

    @override
    async def __async_post_init__(self) -> None:
        self.update_cookies({"LG": "en"})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [] | [""] if _get_file_id(scrape_item.url.query):
                return await self.file(scrape_item)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case [] | [""] if file_id := _get_file_id(url.query):
                return url.with_query(file_id)
            case _:
                return url

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        name, password_protected = await self._request_file(scrape_item.url)
        if password_protected:
            if not scrape_item.password:
                raise PasswordProtectedError
            password = scrape_item.password
        else:
            password = None

        filename, ext = self.get_filename_and_ext(name)
        async with self.downloader._semaphore:
            if self.disabled:
                return

            await self.handle_file(
                scrape_item.url,
                scrape_item,
                name,
                ext,
                custom_filename=filename,
                debrid_link=await self._request_download(scrape_item.url, password),
            )

    async def _request_file(self, url: AbsoluteHttpURL) -> tuple[str, bool]:
        soup = await self.request_soup(url.update_query(lg="en"))
        if soup.select_one(Selector.PREMIUM_REQUIRED):
            raise ScrapeError(401)

        with self.disable_on_error("Rate limited"):
            if tag := soup.select_one(Selector.RATE_LIMITED):
                raise ScrapeError(509, css.text(tag))

        name = css.select_text(soup, Selector.FILENAME)
        password_protected = "pass" in css.parse_form(css.select(soup, "form")).inputs
        return name, password_protected

    async def _request_download(self, url: AbsoluteHttpURL, password: str | None) -> AbsoluteHttpURL:
        data = {"pass": password} if password else {}
        if not self.config.network.ssl_context:
            data["dl_no_ssl"] = "on"

        soup = await self.request_soup(url, method="POST", data=data or None)
        if soup.select_one(Selector.NO_FREE_DOWNLOAD):
            raise ScrapeError(509, "Free download is temporarily disabled. Try again later")

        return self.parse_url(css.select(soup, Selector.DL_LINK, "href"))


def _get_file_id(query: Mapping[str, str]) -> str | None:
    if query:
        name, value = next(iter(query.items()))
        if not value and name.isalnum() and 5 <= len(name) <= 20:
            return name

    return None
