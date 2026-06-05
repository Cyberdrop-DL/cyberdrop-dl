from __future__ import annotations

import dataclasses
import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl import env
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, auto_task_id
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper, extr_text, parse_url

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem

_PREMIUM_SUB_RELEASE_DATE = datetime.datetime(2017, 1, 1, tzinfo=datetime.UTC).timestamp()
# Approx date from https://web.archive.org/web/20170520211342/https://clyp.it/premium-pricing


class ClypItCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Audio": "/<audio_id>",
        "User": "/user/<user_id>",
    }
    DOMAIN: ClassVar[str] = "clyp.it"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://clyp.it")

    def __post_init__(self) -> None:
        self.api: ClypItAPI = ClypItAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [audio_id]:
                return await self.audio(scrape_item, audio_id)
            case ["user", user_id]:
                return await self.user(scrape_item, user_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, user_id: str) -> None:
        scrape_item.setup_as_profile("")
        async for audios in self.api.user_uploads(user_id):
            for audio in audios:
                new_item = scrape_item.create_child(self.PRIMARY_URL / audio.id)
                self.create_task(self._audio_task(new_item, audio))
                scrape_item.add_children()

    @error_handling_wrapper
    async def audio(self, scrape_item: ScrapeItem, audio_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        audio = await self.api.audio(audio_id, token=scrape_item.url.query.get("token"))
        await self._audio(scrape_item, audio)

    async def _audio(self, scrape_item: ScrapeItem, audio: Audio) -> None:
        scrape_item.setup_as_profile(self.create_title(audio.user.full_name, audio.user.id))
        scrape_item.uploaded_at = date = self.parse_iso_date(audio.created_at)
        src = audio.mp3
        if date > _PREMIUM_SUB_RELEASE_DATE:
            src = await self.api.wav(audio.id, token=scrape_item.url.query.get("token")) or src

        _, ext = self.get_filename_and_ext(src.name)
        filename = self.create_custom_filename(audio.title, ext, file_id=audio.id)
        await self.handle_file(src, scrape_item, audio.title, ext, custom_filename=filename, metadata=audio)

    @auto_task_id
    @error_handling_wrapper
    async def _audio_task(self, scrape_item: ScrapeItem, audio: Audio) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        await self._audio(scrape_item, audio)


class ClypItAPI(API):
    # docs: https://clyp.it/api
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.clyp.it")

    async def audio(self, audio_id: str, token: str | None) -> Audio:
        api_url = self.ENTRYPOINT / audio_id / "Playlist"
        if token:
            api_url = api_url.with_query(token=token)

        playlist = await self.request_json(api_url)
        audios = map(_parse_audio, playlist["AudioFiles"])
        return next(a for a in audios if a.id == audio_id)

    async def wav(self, audio_id: str, token: str | None) -> AbsoluteHttpURL | None:
        if env.CLYPIT_PREFER_MP3:
            return None
        url = self.PRIMARY_URL / audio_id
        if token:
            url = url.with_query(token=token)
        text = await self.request_text(url)
        try:
            src = extr_text(text, 'var wavStreamUrl = "', '";')
        except ValueError:
            return None
        else:
            return self.parse_url(src)

    def user_uploads(self, user_id: str) -> AsyncGenerator[map[Audio]]:
        api_url = self.ENTRYPOINT / "User" / user_id / "Uploads"
        return self._pager(api_url)

    async def _pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[map[Audio]]:
        url = url.update_query(count=20)
        while True:
            resp = await self.request_json(url)
            yield map(_parse_audio, resp["Data"])
            next_page: str | None = resp.get("Paging").get("Next")
            if not next_page:
                break
            url = self.parse_url(next_page)


@dataclasses.dataclass(slots=True)
class User:
    id: str
    first_name: str
    last_name: str | None = None

    @property
    def full_name(self) -> str:
        return " ".join(filter(None, (self.first_name, self.last_name)))


@dataclasses.dataclass(slots=True)
class Audio:
    id: str
    title: str
    created_at: str
    user: User
    mp3: AbsoluteHttpURL


def _parse_audio(audio: dict[str, Any]) -> Audio:
    return Audio(
        id=audio["AudioFileId"],
        title=audio["Title"],
        created_at=audio["DateCreated"],
        mp3=parse_url(audio.get("SecureMp3Url") or audio["Mp3Url"]),
        user=_parse_user(audio["User"]),
    )


def _parse_user(user: dict[str, Any]) -> User:
    return User(id=user["UserId"], first_name=user["FirstName"], last_name=user.get("LastName"))
