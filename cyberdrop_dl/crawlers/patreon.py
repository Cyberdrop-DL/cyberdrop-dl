from __future__ import annotations

import contextlib
import dataclasses
import json
from typing import TYPE_CHECKING, Any, ClassVar, NotRequired, TypedDict, TypeGuard, cast, final

from typing_extensions import ReadOnly

from cyberdrop_dl import aio
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, URLConfig, auto_task_id
from cyberdrop_dl.exceptions import MaxChildrenError, NoExtensionError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, next_js, traversal
from cyberdrop_dl.utils._url import URLDeduper
from cyberdrop_dl.utils.dataclass import DictDataclass
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.filepath import Filename
    from cyberdrop_dl.url_objects import ScrapeItem


@dataclasses.dataclass(frozen=True, slots=True, order=True)
class Media:
    id: str
    name: str | None
    url: AbsoluteHttpURL
    attributes: dict[str, Any]
    hash: str | None = None

    __iter__ = DictDataclass.__iter__

    def __json__(self) -> dict[str, Any]:
        me = dict(self)
        del me["attributes"]
        me["url"] = str(self.url)
        return me

    def __post_init__(self) -> None:
        if not self.hash:
            object.__setattr__(self, "hash", _md5_from_url(self.url))


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


@URLConfig(allow_empty_path=True)
class PatreonGenericCrawler(Crawler, is_generic=True):
    # generic cause Patreon allows creators to use a custom domain
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": (
            "/posts/<slug>-<post-id>",
            "/<creator>/posts/<slug>-<post-id>",
        ),
        "Creator": (
            "/<creator>",
            "/cw/<creator>",
        ),
    }

    DOMAIN: ClassVar[str] = "patreon"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.patreon.com")
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} - {title}"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.DOMAIN = PatreonGenericCrawler.DOMAIN  # pyright: ignore[reportConstantRedefinition]

    def __post_init__(self) -> None:
        self.api: PatreonV1API = PatreonV1API.from_crawler(self)

    @property
    def separate_posts(self) -> bool:
        return True

    def is_custom_domain(self) -> bool:
        return self.PRIMARY_URL.host != PatreonCrawler.PRIMARY_URL.host

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["posts", slug] | [_, "posts", slug]:
                post_id = slug.rpartition("-")[-1]
                await self.post(scrape_item, post_id)
            case [_creator] | ["cw", _creator]:
                await self.creator(scrape_item)
            case [] | [""] | ["cw"] if self.is_custom_domain():
                await self.creator(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        post = await self.api.post(post_id)
        await self._post(
            scrape_item,
            post=_flatten_post(post["data"]),
            included=_flatten_included(post["included"]),
        )

    @error_handling_wrapper
    async def _post(self, scrape_item: ScrapeItem, post: Post, included: dict[str, Included]) -> None:
        if not post["current_user_can_view"]:
            raise ScrapeError(402, "You do not have access to this post")

        campaign_name: str = included[post["campaign_id"]]["attributes"]["name"]
        title = self.create_title(campaign_name)
        scrape_item.setup_as_album(title)

        scrape_item.uploaded_at = date = self.parse_iso_date(post["published_at"])
        post_title = self.create_separate_post_title(post["title"], post["id"], date)
        scrape_item.append_folders(post_title)
        self.create_eager_task(self.write_metadata(scrape_item, f"post_{post['id']}", post))
        medias = self._extract_media(post, included)
        await self._post_media(scrape_item, post, medias)

    def _extract_media(self, post: Post, included: dict[str, Included]) -> tuple[Media, ...]:
        medias = tuple(_parse_media(post, included))
        self.log.debug("Found %s media assets in post %s \n%s", len(medias), post["id"], LazyLogMedia(medias))
        return medias

    async def _post_media(self, scrape_item: ScrapeItem, post: Post, medias: tuple[Media, ...]) -> None:  # noqa: C901
        seen_urls: URLDeduper = URLDeduper()
        seen_media_ids: set[str] = set()
        seen_media_hashes: set[str] = set()

        sleep = aio.periodic_sleep(10)

        async def dispatch_url(link: str, *, embed: bool = False) -> None:
            url = self.parse_url(link, self.origin)
            if url in seen_urls:
                return

            if url.host in (self.PRIMARY_URL.host, PatreonGenericCrawler.PRIMARY_URL.host):
                msg = f"Skipping nested thread URL: {url}, parent: {scrape_item.url}"
                await self.raise_exc(url, MaxChildrenError(msg))
                return

            new_item = scrape_item.create_child(url)
            self.handle_external_links(new_item, reset=not embed)
            scrape_item.add_children()
            await sleep()

        async with aio.non_cancelling_taskgroup() as tg:
            for media in medias:
                if media.id in seen_media_ids:
                    continue
                seen_media_ids.add(media.id)
                if media.hash:
                    if media.hash in seen_media_hashes:
                        continue
                    seen_media_hashes.add(media.hash)

                tg.create_task(self._media(scrape_item, media))
                scrape_item.add_children()
                await sleep()

            if embed := post.get("embed"):
                self.log.debug("Found embed in post %s: %s", post["id"], embed)
                tg.create_task(self.write_metadata(scrape_item, f"embed_{post['id']}", embed))
                await dispatch_url(embed["url"], embed=True)

            links, assets = _extract_json_tiptap_media(post)
            if not (links or assets):
                return

            self.log.debug("Found embedded TIPTAP media in post %s: %s", post["id"], {"links": links, "assets": assets})

            for asset in assets:
                if asset["id"] not in seen_media_ids:
                    seen_media_ids.add(asset["id"])
                    tg.create_task(self.media(scrape_item, asset["id"]))
                    scrape_item.add_children()
                    await sleep()

            if not self.config.crawlers.patreon.content_urls:
                return

            for url in links:
                await dispatch_url(url)

    @error_handling_wrapper
    async def media(self, scrape_item: ScrapeItem, media_id: str) -> None:
        media = await self.api.media(media_id)
        await self._media(scrape_item, media)

    @error_handling_wrapper
    async def _media(self, scrape_item: ScrapeItem, media: Media) -> None:
        self.create_eager_task(self.write_metadata(scrape_item, f"media_{media.id}", media))
        if media.url.suffix == ".m3u8":
            return await self._m3u8_media(scrape_item, media)

        original_name, filename = await self._get_media_filename(media)

        await self.handle_file(
            media.url,
            scrape_item,
            original_name,
            filename.suffix,
            custom_filename=self.create_custom_filename(filename.name, filename.suffix, file_id=media.id),
        )

    async def _get_media_filename(self, media: Media) -> tuple[str, Filename]:
        errors: list[Exception] = []
        if media.name and not media.name.startswith(("http:", "https:")):
            try:
                return media.name, self.get_filename_and_ext(media.name)
            except NoExtensionError as e:
                errors.append(e)

        async with self.request(media.url) as resp:
            if name := resp.filename or media.name:
                try:
                    return name, self.get_filename_and_ext(name, mime_type=resp.content_type)
                except NoExtensionError as e:
                    errors.append(e)

        raise ExceptionGroup("No File Extension", tuple(errors))

    async def _m3u8_media(self, scrape_item: ScrapeItem, media: Media) -> None:
        m3u8, info = await self.request_m3u8_playlist(media.url)
        filename = self.create_custom_filename(
            media.hash or media.url.name.removesuffix(".m3u8"),
            ext := ".mp4",
            file_id=media.id,
            resolution=info.resolution,
            video_codec=info.codecs.video,
            audio_codec=info.codecs.audio,
        )
        await self.handle_file(media.url, scrape_item, filename, ext, m3u8=m3u8)

    @error_handling_wrapper
    async def creator(self, scrape_item: ScrapeItem) -> None:
        campaign_id = await self.api.campaign_id(scrape_item.url)
        await self.campaign(scrape_item, campaign_id)

    @error_handling_wrapper
    async def campaign(self, scrape_item: ScrapeItem, campaign_id: str) -> None:
        scrape_item.setup_as_profile("")
        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for resp in self.api.posts(campaign_id):
                included = _flatten_included(resp["included"])
                for post in resp["data"]:
                    post = _flatten_post(post)
                    new_item = scrape_item.create_child(self.parse_url(post["url"], self.origin))
                    tg.create_task(self._post_task(new_item, post, included))
                    scrape_item.add_children()
                    await sleep()

    _post_task = auto_task_id(_post)


@URLConfig(allow_empty_path=False)
class PatreonCrawler(PatreonGenericCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.patreon.com")


class LazyLogMedia:
    def __init__(self, media: tuple[Media, ...]) -> None:
        self.media: tuple[Media, ...] = media

    def __json__(self) -> tuple[dict[str, Any], ...]:
        return tuple(m.__json__() for m in self.media)

    def __str__(self) -> str:
        return "\n".join(map(str, self.__json__()))


@HTTPConfig(impersonate=True)
class PatreonV1API(API):
    # Public API v1 is retiring on October 7, 2026.
    # https://docs.patreon.com/#apiv2-resource-endpoints
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.patreon.com/api")

    async def post(self, post_id: str) -> dict[str, Any]:
        url = (self.ENTRYPOINT / "posts" / post_id).with_query(_API_PARAMS)
        return await self.request_json(url)

    async def media(self, media_id: str) -> Media:
        url = (self.ENTRYPOINT / "media" / media_id).with_query(_API_PARAMS)
        resp = await self.request_json(url)
        attrs = resp["data"]["attributes"]
        if not (url := attrs.get("download_url")):
            raise ScrapeError(403, f"No download URL found for {media_id}")

        return Media(media_id, attrs.get("file_name"), self.parse_url(url, self.origin), attrs)

    async def campaign_id(self, url: AbsoluteHttpURL) -> str:
        async with self.request(url, impersonate=True) as resp:
            soup = await resp.soup()
            with contextlib.suppress(css.SelectorError):
                bootstrap = _extract_bootstrap(soup)
                return bootstrap["campaign"]["data"]["id"]

            with contextlib.suppress(css.SelectorError):
                url = self.parse_url(css.select(soup, "head link[href*='/campaign/']", "href"))
                return url.parts[url.parts.index("campaign") + 1]

            # TODO: fix next_js chunk parsing
            return _extract_campaign_id(await resp.text())

    def posts(self, campaign_id: str) -> AsyncGenerator[dict[str, Any]]:
        url = (
            (self.ENTRYPOINT / "posts")
            .with_query(_API_PARAMS)
            .extend_query(
                {
                    "filter[campaign_id]": campaign_id,
                }
            )
        )
        return self.pager(url)

    async def pager(self, api_url: AbsoluteHttpURL) -> AsyncGenerator[dict[str, Any]]:
        while True:
            resp = await self.request_json(api_url)
            yield resp

            try:
                cursor = resp["meta"]["pagination"]["cursors"]["next"]
            except LookupError:
                break
            if not cursor:
                break
            api_url = api_url.update_query({"page[cursor]": cursor})


def _extract_campaign_id(content: str) -> str:
    for start, end in [
        (r"{\"value\":{\"campaign\":{\"data\":{\"id\":\"", r"\""),
        (r"\"id\":\"NavigationBar_", '\\"'),
    ]:
        try:
            return extr_text(content, start, end)
        except ValueError:
            pass
    raise ScrapeError(422, "Unable to extract campaign id")


def _flatten_included(included: list[Included]) -> dict[str, Included]:
    return {incl["id"]: incl for incl in included}


def _extract_bootstrap(soup: BeautifulSoup) -> dict[str, Any]:
    data = next_js.data(soup)
    envelope = data["props"]["pageProps"]["bootstrapEnvelope"]
    return envelope.get("pageBootstrap") or envelope["bootstrap"]


def _parse_post(post: dict[str, Any]) -> Generator[tuple[str, Any]]:
    yield "id", str(post["id"])
    yield from _parse_attributes(post["attributes"])
    yield "relationships", post["relationships"]
    yield "campaign_id", post["relationships"]["campaign"]["data"]["id"]


def _parse_attributes(attributes: dict[str, Any]) -> Generator[tuple[str, Any]]:
    for name, value in attributes.items():
        if value and name.endswith("_json_string"):
            value = json.loads(value)

        yield name, value


def _extract_json_tiptap_media(post: Post) -> tuple[list[str], list[Included]]:
    links: list[str] = []
    assets: list[Included] = []
    for name, value in post.items():
        if value and name.endswith("_json_string"):
            for _, elem in traversal.traverse(value, _tiptap_media_visitor):
                attrs = elem["attrs"]
                match media_type := elem["type"]:
                    case "link" if href := attrs.get("href"):
                        links.append(href)
                    case "audio" | "video" | "image" if media_id := attrs.get("media_id"):
                        assets.append({"id": media_id, "type": media_type, "attributes": attrs})
                    case _:
                        continue

    return links, assets


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


def _md5_from_url(url: AbsoluteHttpURL) -> str | None:
    for p in reversed(url.parts):
        if len(p) == 32:
            return p


def _parse_media(post: Post, included: dict[str, Included]) -> Generator[Media]:
    if post_file := post.get("post_file"):
        media_id = str(post_file["media_id"])
        url = PatreonCrawler.parse_url(post_file["url"])
        yield Media(media_id, post_file.get("name"), url, post_file)

    for media_id in _get_post_media(post):
        media = included[media_id]
        attributes = media["attributes"]

        if media["type"] == "media" and (url := attributes.get("download_url")):
            yield Media(media_id, attributes.get("file_name"), PatreonCrawler.parse_url(url), attributes)

    if image := post.get("image"):
        url = PatreonCrawler.parse_url(image.get("large_url") or image["url"])
        if m_hash := _md5_from_url(url):
            yield Media(m_hash, None, url, image)


@final
class TipTap:
    ASSET = frozenset({"audio", "link", "video", "image"})
    DOC = frozenset(
        {
            "heading",
            "hardBreak",
            "horizontalRule",
            "listItem",
            "bulletList",
            "orderedList",
            "blockquote",
            "paragraph",
            "text",
            "doc",
        }
    )
    TEXT = frozenset(("italic", "underline", "strike", "bold"))


def _tiptap_media_visitor(_: object, obj: object) -> TypeGuard[dict[str, Any]]:
    if not (type(obj) is dict and (t_type := obj.get("type"))):
        return False

    if t_type in TipTap.ASSET:
        return bool(obj.get("attrs"))

    if not (t_type in TipTap.DOC or t_type in TipTap.TEXT):
        PatreonCrawler.get_logger().warning("Unknown TIPTAP element: %s", obj)

    return False


_API_PARAMS = (
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
                "content_json_string",
                "content",
                "current_user_can_view",
                "embed",
                "image",
                "is_paid",
                "meta_image_url",
                "moderation_status",
                "post_file",
                "post_metadata",
                "post_type",
                "published_at",
                "teaser_text_json_string",
                "teaser_text",
                "thumbnail_url",
                "thumbnail",
                "title",
                "url",
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
