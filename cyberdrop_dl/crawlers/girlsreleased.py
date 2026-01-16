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
            case ["site", domain]:
                return await self.site(scrape_item, domain)
            case ["site", domain, "model", model_id, model_name]:
                return await self.site(scrape_item, domain, model_id, model_name)
            case ["model", model_id, name]:
                return await self.model(scrape_item, model_id, name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def set(self, scrape_item: ScrapeItem, set_id: str) -> None:
        api_url = self.PRIMARY_URL / "api/0.2/set" / set_id
        set_ = Set(**(await self.request_json(api_url))["set"])
        title = self.create_separate_post_title(set_.name, set_id, set_.date)
        title = self.create_title(title, set_id)
        scrape_item.setup_as_album(title, album_id=set_id)
        scrape_item.possible_datetime = set_.date
        for image in set_.images:
            url = self.parse_url(image[3])
            new_scrape_item = scrape_item.create_child(url)
            self.handle_external_links(new_scrape_item, reset=False)
            scrape_item.add_children()

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem, model_id: str, model_name: str) -> None:
        title = self.create_title(f"{model_name} [model]")
        scrape_item.setup_as_profile(title)
        api_base = self.PRIMARY_URL / "api/0.3/sets/model" / model_id
        await self._pagination(scrape_item, api_base)

    @error_handling_wrapper
    async def site(
        self,
        scrape_item: ScrapeItem,
        domain: str,
        model_id: str | None = None,
        model_name: str | None = None,
    ) -> None:
        title = self.create_title(f"{domain} [site]")
        scrape_item.setup_as_profile(title)
        api_base = self.PRIMARY_URL / "api/0.3/sets/site" / domain
        if model_id and model_name:
            api_base = api_base / "model" / model_id
            scrape_item.add_to_parent_title(f"{model_name} [model]")

        await self._pagination(scrape_item, api_base)

    async def _pagination(self, scrape_item: ScrapeItem, api_base: AbsoluteHttpURL) -> None:
        for page in itertools.count(0):
            api_url = api_base / f"page/{page}"
            sets: list[list[int]] = (await self.request_json(api_url))["sets"]

            for set_ in sets:
                set_id = set_[0]
                url = self.PRIMARY_URL / "set" / str(set_id)
                new_scrape_item = scrape_item.create_child(url)
                self.create_task(self.run(new_scrape_item))
                scrape_item.add_children()

            if len(sets) < 80:
                break
