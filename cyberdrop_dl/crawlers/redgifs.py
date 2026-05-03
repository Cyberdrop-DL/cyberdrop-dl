from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Final

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from cyberdrop_dl.clients.response import AbstractResponse
    from cyberdrop_dl.url_objects import ScrapeItem

# Primary URL needs `www.` to prevent redirect
PRIMARY_URL = AbsoluteHttpURL("https://www.redgifs.com/")
API_ENTRYPOINT = AbsoluteHttpURL("https://api.redgifs.com/v2")
_PAGE_LIMIT: Final = 100
_PAGE_COUNT: Final = 100


@dataclasses.dataclass(slots=True, order=True)
class Gif:
    id: str
    create_date: int
    hd: str | None
    sd: str
    title: str | None

    @staticmethod
    def from_dict(gif: dict[str, Any]) -> Gif:
        return Gif(
            id=gif["id"],
            create_date=gif["createDate"],
            sd=gif["urls"]["sd"],
            hd=gif["urls"].get("hd"),
            title=gif.get("title"),
        )


class RedGifsCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "User": "/users/<user>",
        "Gif": "/watch/<gif_id>",
        "Image": "/i/<image_id>",
        "Embeds": "/ifr/<gif_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "redgifs"
    FOLDER_DOMAIN: ClassVar[str] = "RedGifs"
    _RATE_LIMIT: ClassVar[RateLimit] = 2, 3

    @classmethod
    def __json_resp_check__(cls, json_resp: dict[str, Any], resp: AbstractResponse[Any]) -> None:
        if error := json_resp.get("error"):
            msg: str = error.get("description") or error.get("message")
            if error.get("code"):
                msg = f"[{error['code']}] {msg if msg else ''}".strip()
            raise ScrapeError(resp.status, msg)

    def __post_init__(self) -> None:
        self.headers: dict[str, str] = {}

    async def __async_post_init__(self) -> None:
        token_url = API_ENTRYPOINT / "auth/temporary"

        with self.catch_errors(token_url), self.disable_on_error("Unable to get API token"):
            token: str = (await self.request_json(token_url))["token"]
            self.headers["Authorization"] = f"Bearer {token}"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["users", user_name]:
                return await self.user(scrape_item, user_name.lower())
            case ["i" | "watch" | "ifr", gif_id]:
                return await self.gif(scrape_item, _id(gif_id))
            case [_, _] if self.is_self_subdomain(scrape_item.url):
                scrape_item.url = _canonical_url(scrape_item.url.name)
                return await self.gif(scrape_item, scrape_item.url.name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, user_id: str) -> None:
        title = self.create_title(user_id)
        scrape_item.setup_as_album(title)
        init_page = int(scrape_item.url.query.get("page", 1))

        async for gifs in self._profile_pager(user_id, init_page):
            for gif in gifs:
                new_scrape_item = scrape_item.create_child(_canonical_url(gif.id))
                await self._gif(new_scrape_item, gif)
                scrape_item.add_children()

    async def _profile_pager(self, user_id: str, init_page: int = 1) -> AsyncGenerator[tuple[Gif, ...]]:
        gif_ids: set[str] = set()

        def parse_unique_gifs(gifs: list[dict[str, str]]) -> Generator[Gif]:
            for gif_dict in gifs:
                gif = Gif.from_dict(gif_dict)
                if gif.id not in gif_ids:
                    gif_ids.add(gif.id)
                    yield gif

        api_url = API_ENTRYPOINT / "users" / user_id / "search"

        async def pager(*, reverse: bool = False) -> AsyncGenerator[tuple[Gif, ...]]:
            for page in range(1 if reverse else init_page, _PAGE_LIMIT + 1):
                resp: dict[str, Any] = await self.request_json(
                    api_url.with_query(
                        order="old" if reverse else "new",
                        count=_PAGE_COUNT,
                        page=page,
                    ),
                    headers=self.headers,
                )

                gifs = tuple(parse_unique_gifs(resp["gifs"]))
                if not gifs:
                    return

                yield gifs

        async for gifs in pager():
            yield gifs

        # fetch gifs in reverse order to bypass API pagination limit
        async for gifs in pager(reverse=True):
            yield gifs

    @error_handling_wrapper
    async def gif(self, scrape_item: ScrapeItem, gif_id: str) -> None:
        canonical_url = _canonical_url(gif_id)
        if await self.check_complete_from_referer(canonical_url):
            return

        scrape_item.url = canonical_url
        api_url = API_ENTRYPOINT / "gifs" / gif_id
        gif = Gif.from_dict((await self.request_json(api_url, headers=self.headers))["gif"])
        if gif.title:
            scrape_item.setup_as_album(self.create_title(gif.title))
        await self._gif(scrape_item, gif)

    async def _gif(self, scrape_item: ScrapeItem, gif: Gif) -> None:
        src = self.parse_url(gif.hd or gif.sd)
        scrape_item.uploaded_at = gif.create_date
        filename, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(src, scrape_item, filename, ext, metadata=gif)


def _id(name: str) -> str:
    # PaleturquoiseLostStickinsect-mobile.m4s -> paleturquoiseLoststickinsect
    # Id needs to be lower case for requests to the api, but final files (media.redgifs) need each word capitalized
    return name.lower().split(".", 1)[0].split("-", 1)[0]


def _canonical_url(name_or_id: str) -> AbsoluteHttpURL:
    return PRIMARY_URL / "watch" / _id(name_or_id)


def fix_db_referer(referer: str) -> str:
    url = AbsoluteHttpURL(referer)
    name = url.name or url.parent.name
    return str(_canonical_url(name))
