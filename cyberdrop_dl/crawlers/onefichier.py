from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedDomains, SupportedPaths
from cyberdrop_dl.exceptions import PasswordProtectedError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    NO_FREE_DOWNLOAD = ".ct_warn:-soup-contains('Free download is temporarily limited due to high demand')"
    DL_LINK = "a:-soup-contains-own-('Start your download')"
    FILENAME = "table td.normal span[style='font-weight:bold']"
    PREMIUM_REQUIRED = (
        ".ct_warn:-soup-contains-own('The owner of this file has reserved access to the subscribers of our services')"
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
    FOLDER_DOMAIN: ClassVar[str] = "1fichier"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://1fichier.com")
    _DOWNLOAD_SLOTS: ClassVar[int | None] = 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [""] if (file_id := scrape_item.url.query_string).isalnum():
                if not 5 <= len(file_id) <= 20:
                    raise ValueError
                return await self.file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url.update_query(lg="en"))
        if soup.select_one(Selector.PREMIUM_REQUIRED):
            raise ScrapeError(401)

        form = css.parse_form(css.select(soup, "form"))
        if "pass" in form.inputs:
            if not scrape_item.password:
                raise PasswordProtectedError
            form.inputs["pass"] = scrape_item.password

        name = css.select_text(soup, Selector.FILENAME)
        filename, ext = self.get_filename_and_ext(name)
        async with self.downloader._semaphore:
            await self.handle_file(
                scrape_item.url,
                scrape_item,
                name,
                ext,
                custom_filename=filename,
                debrid_link=await self._request_download(scrape_item.url, form.inputs),
            )

    async def _request_download(self, url: AbsoluteHttpURL, data: dict[str, str | None]) -> AbsoluteHttpURL:
        data.pop("save", None)
        if not self.client.ssl_context:
            data["dl_no_ssl"] = "on"
        else:
            del data["dl_no_ssl"]
        soup = await self.request_soup(url.update_query(lg="en"), method="POST", data=data)
        if soup.select_one(Selector.NO_FREE_DOWNLOAD):
            raise ScrapeError(509, "Free download is temporarily disabled. Try again later")

        return self.parse_url(css.select(soup, Selector.DL_LINK, "href"))
