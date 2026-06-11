from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any, ClassVar, NotRequired, TypedDict, cast

from bs4 import BeautifulSoup
from typing_extensions import ReadOnly

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import NoExtensionError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text, next_js

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Generator

    from cyberdrop_dl.url_objects import ScrapeItem


@dataclasses.dataclass(slots=True)
class Media:
    id: str
    name: str | None
    url: AbsoluteHttpURL
    attributes: dict[str, Any]


class Asset(TypedDict):
    id: str
    type: str
    attributes: ReadOnly[NotRequired[dict[str, Any]]]
    relationships: ReadOnly[NotRequired[dict[str, Any]]]


class Included(Asset):
    attributes: dict[str, Any]


class Post(Included):
    relationships: dict[str, Any]

    current_user_can_view: bool
    campaign_id: str
    published_at: str
    title: str
    url: str


class PatreonCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/posts/<slug>",
        "Creator": (
            "/<creator>",
            "/cw/<creator>",
        ),
    }

    DOMAIN: ClassVar[str] = "patreon"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.patreon.com")
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} - {title}"

    @property
    def separate_posts(self) -> bool:
        return True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["posts", _]:
                return await self.post(scrape_item)
            case [creator] | ["cw", creator]:
                return await self.creator(scrape_item, creator)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url, impersonate=True)
        post: dict[str, Any] = _extract_bootstrap(soup)["post"]
        self._post(
            scrape_item,
            post=_flatten_post(post["data"]),
            included=_flatten_included(post["included"]),
        )

    @error_handling_wrapper
    def _post(self, scrape_item: ScrapeItem, post: Post, included: dict[str, Included]) -> None:
        if not post["current_user_can_view"]:
            raise ScrapeError(402, "You do not have access to this post")

        campaign_name: str = included[post["campaign_id"]]["attributes"]["name"]
        title = self.create_title(campaign_name)
        scrape_item.setup_as_album(title)

        scrape_item.uploaded_at = date = self.parse_iso_date(post["published_at"])
        post_title = self.create_separate_post_title(post["title"], post["id"], date)
        scrape_item.append_folders(post_title)

        self.create_task(self.write_metadata(scrape_item, f"post_{post['id']}", post))
        for media in self._parse_media(post, included):
            self.create_task(self._media(scrape_item, media))
            self.create_task(self.write_metadata(scrape_item, f"media_{media.id}", media))
            scrape_item.add_children()

        if embed := post.get("embed"):
            new_item = scrape_item.create_child(self.parse_url(embed["url"]))
            self.handle_embed(new_item)
            self.create_task(self.write_metadata(scrape_item, f"embed_{post['id']}", embed))
            scrape_item.add_children()

    @error_handling_wrapper
    async def _media(self, scrape_item: ScrapeItem, media: Media) -> None:
        if media.url.suffix == ".m3u8":
            return await self._m3u8_media(scrape_item, media)

        name = media.name
        if not name:
            async with self.request(media.url) as resp:
                name = resp.content_disposition.filename

        try:
            filename, ext = self.get_filename_and_ext(name)
        except NoExtensionError:
            name = media.url.name
            filename, ext = self.get_filename_and_ext(name)

        await self.handle_file(media.url, scrape_item, name, ext, custom_filename=filename)

    async def _m3u8_media(self, scrape_item: ScrapeItem, media: Media) -> None:
        m3u8, info = await self.request_m3u8_playlist(media.url)
        filename = self.create_custom_filename(
            media.url.name.removesuffix(".m3u8"),
            ext := ".mp4",
            resolution=info.resolution,
            video_codec=info.codecs.video,
            audio_codec=info.codecs.audio,
        )
        await self.handle_file(media.url, scrape_item, filename, ext, m3u8=m3u8)

    def _parse_media(self, post: Post, included: dict[str, Included]) -> Generator[Media]:
        media_ids: set[str] = set()
        if post_file := post.get("post_file"):
            media_id = str(post_file["media_id"])
            media_ids.add(media_id)
            url = self.parse_url(post_file["url"])
            yield Media(media_id, post_file.get("name"), url, post_file)

        for media_id in _get_post_media(post):
            media = included[media_id]
            attributes = media["attributes"]

            if media["type"] == "media" and (url := attributes.get("download_url")) and media_id not in media_ids:
                media_ids.add(media_id)
                yield Media(media_id, attributes.get("file_name"), self.parse_url(url), attributes)

        return
        # TODO: convert tiptap JSON to HTML or extract media ids from tiptap
        if not post["content"]:
            return
        soup = BeautifulSoup(post["content"], "html.parser")
        for media_id in css.iselect(soup, "[data-media-id]", "data-media-id"):
            if media_id in media_ids:
                continue
            self.log.warning("Found extra media id %s", media_id)
            media_ids.add(media_id)

    @error_handling_wrapper
    async def creator(self, scrape_item: ScrapeItem, creator: str) -> None:
        campaign_id = await self._get_campaign_id(creator)
        await self.campaign(scrape_item, campaign_id)

    @error_handling_wrapper
    async def campaign(self, scrape_item: ScrapeItem, campaign_id: str) -> None:
        scrape_item.setup_as_profile("")
        api_url = (
            (self.PRIMARY_URL / "api/posts")
            .with_query(_CAMPAIGN_API_PARAMS)
            .extend_query(
                {
                    "filter[campaign_id]": campaign_id,
                }
            )
        )
        async for resp in self._api_pager(api_url):
            included = _flatten_included(resp["included"])
            for post in resp["data"]:
                post = _flatten_post(post)
                new_item = scrape_item.create_child(self.parse_url(post["url"]))
                self._post(new_item, post, included)
                scrape_item.add_children()

    async def _api_pager(self, api_url: AbsoluteHttpURL) -> AsyncIterator[dict[str, Any]]:
        while True:
            resp = await self.request_json(api_url, impersonate=True)
            yield resp

            try:
                cursor = resp["meta"]["pagination"]["cursors"]["next"]
            except LookupError:
                break
            if not cursor:
                break
            api_url = api_url.update_query({"page[cursor]": cursor})

    async def _get_campaign_id(self, creator: str) -> str:
        soup = await self.request_soup(self.PRIMARY_URL / creator, impersonate=True)
        try:
            bootstrap = _extract_bootstrap(soup)
        except css.SelectorError:
            # TODO: fix next_js chunk parsing
            return _extract_campaign_id(soup)
        else:
            return bootstrap["campaign"]["data"]["id"]


def _extract_campaign_id(soup: BeautifulSoup) -> str:
    return extr_text(str(soup), r"{\"value\":{\"campaign\":{\"data\":{\"id\":\"", r"\"")


def _extract_campaign_id_next_js(soup: BeautifulSoup) -> str:
    included = next_js.ifind(next_js.extract(soup), "id", "type", "attributes")
    return next(incl["id"] for incl in included if incl["type"] == "campaign")


def _flatten_included(included: list[Included]) -> dict[str, Included]:
    return {incl["id"]: incl for incl in included}


def _extract_bootstrap(soup: BeautifulSoup) -> dict[str, Any]:
    data = json.loads(css.select_text(soup, "#__NEXT_DATA__"))
    envelope = data["props"]["pageProps"]["bootstrapEnvelope"]
    return envelope.get("pageBootstrap") or envelope["bootstrap"]


def _parse_post(post: dict[str, Any]) -> Generator[tuple[str, Any]]:
    yield "id", str(post["id"])
    yield from _parse_attributes(post["attributes"])
    yield "relationships", post["relationships"]
    yield "campaign_id", post["relationships"]["campaign"]["data"]["id"]


def _parse_attributes(attributes: dict[str, Any]) -> Generator[tuple[str, Any]]:
    json_string = "_json_string"
    json_keys = tuple(key for key in attributes if key.endswith(json_string))

    for json_key in json_keys:
        name = json_key.removesuffix(json_string)
        value = attributes.pop(name, None)
        json_value = attributes.pop(json_key, None)
        # TODO: convert to html
        if not value and json_value:
            value = json.loads(json_value)

        yield name, value

    yield from attributes.items()


def _flatten_post(post: dict[str, Any]) -> Post:
    return cast("Post", dict(sorted(_parse_post(post))))  # pyright: ignore[reportInvalidCast]


def _get_post_media(post: Post) -> Generator[str]:
    for name in ("media", "video", "audio", "images", "attachments", "attachments_media"):
        relationships = post["relationships"].get(name, {}).get("data")
        if not relationships:
            continue

        if type(relationships) is not list:
            relationships = [relationships]

        for asset in relationships:
            yield asset["id"]


_CAMPAIGN_API_PARAMS = (
    (
        "include",
        ",".join(
            (
                "campaign",
                "attachments",
                "attachments_media",
                "audio",
                "video",
                "images",
                "media",
                "native_video_insights",
                "user",
            )
        ),
    ),
    (
        "fields[campaign]",
        ",".join(
            (
                "currency",
                "show_audio_post_download_links",
                "avatar_photo_url",
                "avatar_photo_image_urls",
                "is_nsfw",
                "is_monthly",
                "name",
                "url",
            )
        ),
    ),
    (
        "fields[post]",
        ",".join(
            (
                "content",
                "content_json_string",
                "current_user_can_view",
                "embed",
                "image",
                "is_paid",
                "meta_image_url",
                "post_file",
                "post_metadata",
                "published_at",
                "post_type",
                "thumbnail",
                "thumbnail_url",
                "teaser_text",
                "title",
                "url",
                "moderation_status",
            )
        ),
    ),
    (
        "fields[user]",
        ",".join(
            (
                "image_url",
                "full_name",
                "url",
            )
        ),
    ),
    (
        "fields[media]",
        ",".join(
            (
                "id",
                "image_urls",
                "download_url",
                "metadata",
                "file_name",
            )
        ),
    ),
    ("sort", "-published_at"),
    ("filter[is_draft]", "false"),
    ("json-api-version", "1.0"),
)
