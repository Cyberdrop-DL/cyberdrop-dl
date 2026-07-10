from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any, ClassVar, Self

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import extr_text
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cyberdrop_dl.url_objects import ScrapeItem

_PICS = AbsoluteHttpURL("https://pics.wikifeet.com")


class WikiFeetCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Celeb": "/<name>"}
    DOMAIN: ClassVar[str] = "wikifeet"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://wikifeet.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [name]:
                if ".jpg" in name:
                    return await self.direct_file(scrape_item)
                return await self.celeb(scrape_item, name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def celeb(self, scrape_item: ScrapeItem, name: str) -> None:
        html = await self.request_text(self.PRIMARY_URL / name)
        celeb = Celeb.parse(html)
        title = self.create_title(celeb.name)
        slug = celeb.name.replace(" ", "-")
        scrape_item.setup_as_album(title, album_id=slug)
        self.create_eager_task(self.write_metadata(scrape_item, name, celeb))

        sleep = aio.periodic_sleep(100)
        for photo in celeb.photos:
            src = _PICS / f"{slug}-Feet-{photo.id}.jpg"
            self.create_eager_task(self.direct_file(scrape_item, src))
            scrape_item.add_children()
            await sleep()


class WikiFeetMenCrawler(WikiFeetCrawler):
    DOMAIN: ClassVar[str] = "men.wikifeet"
    FOLDER_DOMAIN: ClassVar[str] = "Wikifeet Men"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://men.wikifeet.com")


class WikiFeetXCrawler(WikiFeetCrawler):
    DOMAIN: ClassVar[str] = "wikifeetx"
    FOLDER_DOMAIN: ClassVar[str] = "Wikifeet X"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://wikifeetx.com")


@dataclasses.dataclass(slots=True, kw_only=True)
class Photo:
    TAGS: ClassVar[Mapping[str, str]] = {
        "A": "Arches",
        "B": "Barefoot",
        "C": "Close-up",
        "N": "Nylons",
        "S": "Soles",
        "T": "Toes",
    }
    id: int
    width: int
    height: int
    tags: tuple[str, ...]

    @classmethod
    def parse(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            id=data["pid"],
            width=data["pw"],
            height=data["ph"],
            tags=tuple(tag for tag_id in sorted(data["tags"]) if (tag := cls.TAGS.get(tag_id))),
        )


@dataclasses.dataclass(slots=True, kw_only=True)
class Celeb:
    name: str
    height_us: str
    birthplace: str
    birthday: str
    shoe_size: int
    score: int
    photos: tuple[Photo, ...]

    @classmethod
    def parse(cls, html: str) -> Self:
        content = extr_text(html, "tdata = ", "tbody").rstrip(";")
        data = json.loads(content)
        return cls(
            name=data["cname"],
            birthplace=data["bplace"],
            birthday=data["bdate"],
            shoe_size=data["ssize"],
            score=data["score"],
            height_us=data["height_us"],
            photos=tuple(map(Photo.parse, data["gallery"])),
        )
