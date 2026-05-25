from __future__ import annotations

import dataclasses
from typing import Any, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import DictDataclass, error_handling_wrapper


class ACastCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Show": "/<show_id>",
        "Episode": "/<show_id>/<episode_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.acast.com")
    DOMAIN: ClassVar[str] = "acast.com"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [show, episode_id]:
                return await self.episode(scrape_item, show, episode_id)
            case [show]:
                return await self.show(scrape_item, show)
            case _:
                raise ValueError

    def __post_init__(self) -> None:
        self.api: ACastAPI = ACastAPI(self)

    @error_handling_wrapper
    async def show(self, scrape_item: ScrapeItem, show_id: str) -> None:
        show = await self.api.show(show_id)
        scrape_item.setup_as_album(self.create_title(show.title))
        for ep in map(Episode.from_dict, show.episodes):
            ep.show = show.title
            new_item = scrape_item.create_child(self.parse_url(ep.link))
            self.create_task(self._episode(new_item, ep))
            scrape_item.add_children()

    @error_handling_wrapper
    async def episode(self, scrape_item: ScrapeItem, show: str, episode_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return
        episode = await self.api.episode(show, episode_id)
        scrape_item.setup_as_album(self.create_title(episode.show))
        await self._episode(scrape_item, episode)

    @error_handling_wrapper
    async def _episode(self, scrape_item: ScrapeItem, ep: Episode) -> None:
        title = f"S{ep.season}E{ep.episode} - {ep.title}"
        src = self.parse_url(ep.url)
        scrape_item.uploaded_at = self.parse_iso_date(ep.publishDate)
        _, ext = self.get_filename_and_ext(src.name)
        filename = self.create_custom_filename(title, ext)
        await self.handle_file(src, scrape_item, filename, ext, metadata=ep)


@dataclasses.dataclass(slots=True)
class Episode(DictDataclass):
    id: str
    title: str
    url: str
    publishDate: str  # noqa: N815
    season: int
    episode: int
    link: str
    show: str = dataclasses.field(init=False)


@dataclasses.dataclass(slots=True)
class Show(DictDataclass):
    title: str
    episodes: list[dict[str, Any]]


class ACastAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://feeder.acast.com/api/v1")

    async def episode(self, show: str, episode_id: str) -> Episode:
        api_url = self.ENTRYPOINT / "shows" / show / "episodes" / episode_id
        resp = await self.request_json(api_url.with_query(showInfo="true"))
        ep = Episode.from_dict(resp)
        ep.show = resp["show"]["title"]
        return ep

    async def show(self, show: str) -> Show:
        api_url = self.ENTRYPOINT / "shows" / show
        resp = await self.request_json(api_url)
        return Show.from_dict(resp)
