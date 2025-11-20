from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import dataclasses

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


@dataclasses.dataclass(frozen=True, slots=True)
class Set:
    id: str
    date: int | None
    name: str | None
    site: str
    images: list[list[Any]]


class GirlsReleasedCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Model": "/model/<model_id>/<model_name>",
        "Set": "/set/<set_id>",
        "Site": "/site/<site>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.girlsreleased.com")
    DOMAIN: ClassVar[str] = "girlsreleased"
    FOLDER_DOMAIN: ClassVar[str] = "GirlsReleased"
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} - {id} - {title}"

    @property
    def separate_posts(self) -> bool:
        return True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["set", set_id]:
                return await self.set(scrape_item, set_id)
            case ["site" as category, name]:
                return await self.category(scrape_item, category, name)
            case ["model" as category, _, name]:
                return await self.category(scrape_item, category, name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def set(self, scrape_item: ScrapeItem, set_id: str) -> None:
        api_url = self.PRIMARY_URL / "api/0.2/set" / set_id
        set_ = Set(**(await self.request_json(api_url))["set"])
        title = self.create_separate_post_title(set_.name, set_id, set_.date)
        scrape_item.setup_as_album(title, album_id=set_id)
        scrape_item.possible_datetime = set_.date
        for image in set_.images:
            url = self.parse_url(image[3])
            new_scrape_item = scrape_item.create_child(url)
            self.handle_external_links(new_scrape_item)
            scrape_item.add_children()

    @error_handling_wrapper
    async def category(self, scrape_item: ScrapeItem, category: str, name: str) -> None:
        api_base = self.PRIMARY_URL / "api/0.3/sets" / category / name / "page"
        title = self.create_title(f"{name} [{category}]")
        scrape_item.setup_as_profile(title)

        for page in itertools.count(0):
            api_url = api_base / str(page)
            sets: list[list[int]] = (await self.request_json(api_url))["sets"]

            for set_ in sets:
                set_id = set_[0]
                url = self.PRIMARY_URL / "set" / str(set_id)
                new_scrape_item = scrape_item.create_child(url)
                self.create_task(self.run(new_scrape_item))
                scrape_item.add_children()

            if len(sets) < 80:
                break
