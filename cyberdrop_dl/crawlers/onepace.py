from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import dataclasses

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, next_js
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class PlayGroup:
    sub: str | None
    dub: str
    items: list[Playlist]


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class Playlist:
    id: str
    resolution: int
    url: AbsoluteHttpURL


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
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

    def __post_init__(self) -> None:
        self._langs: tuple[str, str] = ("ja", "en") if self.config.crawlers.one_pace.prefer_dub else ("en", "ja")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [*_, "watch"]:
                await self.all_episodes(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def all_episodes(self, scrape_item: ScrapeItem) -> None:
        html = await self.request_html(self.PRIMARY_URL / "en/watch")
        episodes = await _extract_episodes(html)
        scrape_item.setup_as_profile(self.FOLDER_DOMAIN)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            tg.create_task(self.write_metadata(scrape_item, "one_pace_episodes", {"episodes": episodes}))
            for episode in (Episode(**ep) for ep in episodes):
                url = scrape_item.url.with_fragment(episode.slug)
                self._episode(scrape_item.create_child(url), episode)
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    def _episode(self, scrape_item: ScrapeItem, ep: Episode) -> None:

        def score(group: PlayGroup) -> tuple[int, int]:
            dub_score = self._langs.index(group.dub)
            sub_score = (None, "en").index(group.sub)
            return dub_score, sub_score

        best_group = max(ep.playlistGroups, key=score)
        self.log.info(
            "Downloading %s with subs=%s and lang=%s",
            scrape_item.url,
            best_group.sub,
            best_group.dub,
        )
        best_playlist = max(best_group.items, key=lambda x: x.resolution)
        self.handle_embed(scrape_item.create_child(best_playlist.url))


async def _extract_episodes(html: str) -> list[dict[str, Any]]:
    next_data = await asyncio.to_thread(next_js.extract, await css.asoup(html, parse_only="script"))
    return [_flatten_episode(ep) for ep in next_js.ifind(next_data, "slug", "title", "playlistGroups")]


def _flatten_episode(ep: dict[str, Any]) -> dict[str, Any]:
    ep["backdrops"] = [
        {name: v for name, v in backdrop.items() if not name.startswith("blur")} for backdrop in ep["backdrops"]
    ]
    for group in ep["playlistGroups"]:
        for playlist in group["items"]:
            playlist["url"] = _PD_BASE / playlist["id"]

    return ep
