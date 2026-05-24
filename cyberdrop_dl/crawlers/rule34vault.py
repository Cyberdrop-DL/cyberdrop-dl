from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import DictDataclass, error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


class Rule34VaultCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/post/...",
        "Playlist": "/playlists/view/...",
        "Tag": "/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://rule34vault.com")
    DOMAIN: ClassVar[str] = "rule34vault"
    FOLDER_DOMAIN: ClassVar[str] = "Rule34Vault"

    def __post_init__(self) -> None:
        self.api: R34VaultAPI = R34VaultAPI(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["post", post_id]:
                return await self.post(scrape_item, post_id)
            case ["playlists", playlist_id]:
                return await self.playlist(scrape_item, playlist_id)
            case [tags]:
                return await self.tags(scrape_item, *tags.split(r"|"))
            case _:
                raise ValueError

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, playlist_id: str) -> None:

        playlist = await self.api.playlist(playlist_id)
        title = self.create_title(f"{playlist.title} [playlist]", album_id=playlist_id)
        scrape_item.setup_as_album(title, album_id=playlist_id)

        async for items in self.api.playlist_posts(playlist_id, cursor=scrape_item.url.query.get("cursor")):
            for post in map(Post.from_dict, items):
                new_item = scrape_item.create_child(self.PRIMARY_URL / "post" / str(post.id))
                self.create_task(self._post(new_item, post))
                scrape_item.add_children()

    @error_handling_wrapper
    async def tags(self, scrape_item: ScrapeItem, *tags: str) -> None:
        tags = tuple(t.replace("_", " ") for t in tags)
        title = self.create_title(",".join(tags) + " [tags]")
        scrape_item.setup_as_album(title)

        async for items in self.api.tags(tags, cursor=scrape_item.url.query.get("cursor")):
            for post in map(Post.from_dict, items):
                new_item = scrape_item.create_child(self.PRIMARY_URL / "post" / str(post.id))
                self.create_task(self._post(new_item, post))
                scrape_item.add_children()

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        canonical_url = self.PRIMARY_URL / "post" / post_id
        if await self.check_complete_from_referer(canonical_url):
            return

        post = await self.api.post(post_id)
        await self._post(scrape_item, post)

    @error_handling_wrapper
    async def _post(self, scrape_item: ScrapeItem, post: Post) -> None:
        scrape_item.url = self.PRIMARY_URL / "post" / str(post.id)
        scrape_item.uploaded_at = self.parse_iso_date(post.created)
        await self.direct_file(scrape_item, post.src)


@dataclasses.dataclass(slots=True)
class Post(DictDataclass):
    id: int
    created: str
    type: int
    suffix: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.suffix = ".jpg" if self.type == 0 else ".mp4"

    @property
    def src(self) -> AbsoluteHttpURL:
        return Rule34VaultCrawler.PRIMARY_URL / f"posts/{self.id // 1000}/{self.id}/{self.id}{self.suffix}"


@dataclasses.dataclass(slots=True)
class Playlist(DictDataclass):
    id: int
    created: str
    title: str


class R34VaultAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://rule34vault.com/api/v2")

    async def post(self, post_id: str) -> Post:
        post = await self.request_json(self.ENTRYPOINT / "post" / post_id)
        return Post.from_dict(post)

    async def playlist(self, playlist_id: str) -> Playlist:
        api_url = self.ENTRYPOINT / "playlist" / playlist_id
        playlist = await self.request_json(api_url)
        return Playlist.from_dict(playlist)

    def tags(self, tags: tuple[str, ...], cursor: str | None) -> AsyncGenerator[list[dict[str, Any]]]:
        api_url = self.ENTRYPOINT / "post/search/root"
        return self._pager(api_url, cursor=cursor, includeTags=tags)

    def playlist_posts(self, playlist_id: str, cursor: str | None) -> AsyncGenerator[list[dict[str, Any]]]:
        api_url = self.ENTRYPOINT / "post/search/playlist" / playlist_id
        return self._pager(api_url, cursor=cursor)

    async def _pager(
        self, url: AbsoluteHttpURL, cursor: str | None, **params: Any
    ) -> AsyncGenerator[list[dict[str, Any]]]:
        params = {"CountTotal": False, "Skip": 0, "take": 100} | (params)
        if cursor:
            params["cursor"] = cursor

        while True:
            resp = await self.request_json(url, method="POST", json=params)
            yield resp["items"]

            if len(resp["items"]) < 100:
                return

            params["cursor"] = resp.get("cursor")
            params["Skip"] += params["take"]
