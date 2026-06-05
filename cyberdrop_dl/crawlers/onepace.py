from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import dataclasses

from cyberdrop_dl import env
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper, next_js

if TYPE_CHECKING:
    from collections.abc import Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


@dataclasses.dataclass(slots=True)
class PlayGroup:
    sub: str | None
    dub: str
    playlists: list[Playlist]

    @property
    def score(self) -> tuple[int, int]:
        langs = ("ja", "en") if env.ONEPACE_PREFER_DUB else ("en", "ja")
        return langs.index(self.dub), (None, "en").index(self.sub)


@dataclasses.dataclass(slots=True)
class Playlist:
    id: str
    resolution: int
    url: AbsoluteHttpURL


@dataclasses.dataclass(slots=True)
class Episode:
    title: str
    slug: str
    playlistGroups: list[PlayGroup]  # noqa: N815


_PD_BASE = AbsoluteHttpURL("https://pixeldrain.com/l/")


class OnePaceCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"All episodes": "/watch"}
    DOMAIN: ClassVar[str] = "onepace.net"
    FOLDER_DOMAIN: ClassVar[str] = "OnePace"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://onepace.net")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [*_, "watch"]:
                return await self.all_episodes(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def all_episodes(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(self.PRIMARY_URL / "en/watch")
        episodes = tuple(_extract_episodes(soup))

        await self.write_metadata(scrape_item, "one_pace_episodes", {"episodes": episodes})
        scrape_item.setup_as_profile(self.FOLDER_DOMAIN)
        for episode in (Episode(**ep) for ep in episodes):
            url = scrape_item.url.with_fragment(episode.slug)
            new_item = scrape_item.create_child(url)
            self._episode(new_item, episode)
            scrape_item.add_children()

    @error_handling_wrapper
    def _episode(self, scrape_item: ScrapeItem, ep: Episode) -> None:
        best_group = max(ep.playlistGroups, key=lambda x: x.score)
        self.log.info(
            "Downloading %s with subs=%s and lang=%s",
            scrape_item.url,
            best_group.sub,
            best_group.dub,
        )
        best_playlist = max(best_group.playlists, key=lambda x: x.resolution)
        self.handle_embed(scrape_item.create_child(best_playlist.url))


def _extract_episodes(soup: BeautifulSoup) -> Generator[dict[str, Any]]:
    next_data = next_js.extract(soup)
    for ep in next_js.ifind(next_data, "slug", "title", "playlistGroups"):
        yield _flatten_episode(ep)


def _flatten_episode(ep: dict[str, Any]) -> dict[str, Any]:
    ep["backdrops"] = [
        {name: v for name, v in backdrop.items() if not name.startswith("blur")} for backdrop in ep["backdrops"]
    ]
    for group in ep["playlistGroups"]:
        for playlist in group["playlists"]:
            playlist["url"] = _PD_BASE / playlist["id"]

    return ep
