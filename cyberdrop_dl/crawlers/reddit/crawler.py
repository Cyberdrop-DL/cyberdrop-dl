from __future__ import annotations

import itertools
import mimetypes
from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths, auto_task_id
from cyberdrop_dl.crawlers.reddit.api import ArcticShiftAPI, SearchQuery
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.mediaprops import Subtitle
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css, unique
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import is_within_domain, parse_http_url, remove_query_params

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Generator, Iterable

    from cyberdrop_dl.config.crawlers import RedditConfig
    from cyberdrop_dl.crawlers.reddit.types import Submission
    from cyberdrop_dl.url_objects import ScrapeItem


class RedditImagesCrawler(Crawler, wiki_site="RedditImages"):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "preview.redd.it",
        "cf.preview.redd.it",
        "external-preview.redd.it",
        "i.redd.it",
    )
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Image": "i.redd.it/<id>.>ext>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://i.redd.it")
    DOMAIN: ClassVar[str] = "i.redd.it"
    FOLDER_DOMAIN: ClassVar[str] = "Reddit"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = "i.reddituploads.com", "i.redditmedia.com"

    @staticmethod
    @override
    def __db_path__(url: AbsoluteHttpURL, /) -> str:
        if url.host == "i.redd.it":
            url = url.update_query(None)
        return str(url)

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if url.host in {"preview.redd.it", "cf.preview.redd.it"}:
            url = url.with_host(cls.PRIMARY_URL.host).with_name(url.name.rpartition("-")[-1], keep_query=False)

        if url.host == cls.PRIMARY_URL.host:
            url = url.with_query(None)

        elif "external" not in url.host:
            url = remove_query_params(url, keep=("s",))

        return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if not scrape_item.url.suffix:
            await self.resolve(scrape_item)
        else:
            await self.direct_file(scrape_item)

    @error_handling_wrapper
    async def resolve(self, scrape_item: ScrapeItem) -> None:
        new_url = await self._resolve(scrape_item.url)
        if new_url == scrape_item.url:
            raise ScrapeError(422, "Infinite redirect")

        if not new_url.suffix:
            raise ScrapeError(404, f"Unable to resolve media for {scrape_item.url} ({new_url})")
        with scrape_item.track_changes:
            scrape_item.url = new_url

        await self.direct_file(scrape_item)

    async def _resolve(self, media_url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        # This only works for images in a gallery (multi images post)
        soup = await self.request_soup((RedditCrawler.PRIMARY_URL / "media").update_query(url=str(media_url)))
        try:
            gallery = css.select(soup, "#canonical-url-updater", "value")
        except css.SelectorError:
            raise ScrapeError(422, f"Unable to get extension for {media_url}") from None

        media_id = media_url.name
        media_resolved = css.select(soup, f"img[src*='/{media_id}.']", "src")
        media_resolved_url = self.transform_url(self.parse_url(media_resolved))
        self.log.debug("Resolved %s to %s [%s]", media_url, media_resolved_url, gallery)
        return media_resolved_url

    @override
    def _prepare_headers(self, scrape_item: ScrapeItem) -> dict[str, str]:
        return super()._prepare_headers(scrape_item) | {
            "Accept": "image/*",
            "Referer": "https://www.reddit.com",
        }


@Crawler.db_path_builder("url")
class RedditVideoCrawler(Crawler, wiki_site="RedditVideos"):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "v.redd.it", "packaged-media.redd.it"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "v.redd.it/<video_id>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://v.redd.it")
    DOMAIN: ClassVar[str] = "v.redd.it"
    FOLDER_DOMAIN: ClassVar[str] = "Reddit"

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url).with_query(None)
        match url.parts[1:]:
            case [video_id, *_]:
                return cls.PRIMARY_URL / video_id
            case _:
                return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [video_id, *_]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        m3u8_url = self.PRIMARY_URL / video_id / "HLSPlaylist.m3u8"
        if self.was_scrapped_before(m3u8_url):
            return

        if await self.check_complete(m3u8_url):
            return

        m3u8, info = await self.request_m3u8_playlist(m3u8_url)
        filename = self.create_custom_filename(
            video_id,
            ext := ".mp4",
            resolution=info and info.resolution,
            video_codec=info and info.codecs.video,
            audio_codec=info and info.codecs.audio,
        )
        await self.handle_file(m3u8_url, scrape_item, video_id, ext, m3u8=m3u8, custom_filename=filename)
        self.handle_subs(scrape_item, filename, [Subtitle(m3u8_url.with_name("wh_ben_en.vtt"), lang_code="en")])


class RedditCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "User submissions": (
            "/u/<user>",
            "/u/<user>/submitted",
            "/user/<user>",
            "/user/<user>/submitted",
        ),
        "Subreddit:": "/r/<subreddit>",
        "Submission": (
            "/comments/<id>",
            "/r/<subreddit>/comments/<id>/...",
            "/user/<user>/comments/<id>/...",
        ),
        "Media": "/link/...",
        "Redirects": (
            "/gallery/<id>",
            "/r/<subreddit>/s/<share_id>",
            "/u/<user>/s/<share_id>",
            "/user/<user>/s/<share_id>",
            "/media?url=<url>",
            "out.reddit.com/?url=<url>",
        ),
    }
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{title} - {id}"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.reddit.com")
    DOMAIN: ClassVar[str] = "reddit"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = "www.old.reddit.com", "old.reddit.com"

    def __post_init__(self) -> None:
        self.api: ArcticShiftAPI = ArcticShiftAPI.from_crawler(self)

    @property
    @override
    def separate_posts(self) -> bool:
        return True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["u" | "user", user] | ["u" | "user", user, "submitted"]:
                await self.user(scrape_item, user)
            case ["r", subreddit]:
                await self.subreddit(scrape_item, subreddit)
            case ["r" | "user" | "u", _, "comments", post_id, *_] | ["comments", post_id]:
                await self.submission(scrape_item, post_id)
            case ["gallery", _] | ["r" | "u" | "user", _, "s", _, *_]:
                await self.follow_redirect(scrape_item)
            case ["media"] if url := scrape_item.url.query.get("url"):
                self.redirect(scrape_item, url)
            case ["link", _, "video", video_id, *_]:
                with scrape_item.track_changes:
                    scrape_item.url = RedditVideoCrawler.PRIMARY_URL / video_id
                self.handle_embed(scrape_item)
            case _:
                if scrape_item.url.host == "out.reddit.com" and (url := scrape_item.url.query.get("url")):
                    self.redirect(scrape_item, url)
                else:
                    raise ValueError

    @error_handling_wrapper
    def redirect(self, scrape_item: ScrapeItem, url: str) -> None:
        with scrape_item.track_changes:
            scrape_item.url = self.parse_url(url)
        self.handle_embed(scrape_item)

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, username: str) -> None:
        scrape_item.setup_as_profile(self.create_title(username))
        await self._iter_posts(
            scrape_item,
            self.api.posts_search(
                SearchQuery(
                    author=username,
                    after=self.config.filters.after,
                    before=self.config.filters.before,
                )
            ),
        )

    @error_handling_wrapper
    async def subreddit(self, scrape_item: ScrapeItem, subreddit: str) -> None:
        scrape_item.setup_as_profile(self.create_title(subreddit))
        await self._iter_posts(
            scrape_item,
            self.api.posts_search(
                SearchQuery(
                    subreddit=subreddit,
                    after=self.config.filters.after,
                    before=self.config.filters.before,
                )
            ),
        )

    async def _iter_posts(self, scrape_item: ScrapeItem, submissions: AsyncIterable[Iterable[Submission]]) -> None:
        sleep = aio.periodic_sleep(10)
        async with aio.maybe_aclosing(submissions) as pages:
            async for posts in pages:
                async with aio.non_cancelling_taskgroup() as tg:
                    for post in posts:
                        new_item = scrape_item.create_child(self.parse_url(post["permalink"]))
                        tg.create_task(self._post_task(new_item, post))
                        scrape_item.add_children()
                        await sleep()

    async def _post(self, scrape_item: ScrapeItem, post: Submission) -> None:
        scrape_item.uploaded_at = post["created_utc"]
        title = self.create_separate_post_title(post["title"], post["id"], post["created_utc"])
        scrape_item.setup_as_post(self.create_title(title))
        self.create_eager_task(self.write_metadata(scrape_item, post["id"], post))

        conf = self.config.crawlers.reddit
        if not conf.crossposts and (c_parent := post.get("crosspost_parent")):
            self.log.warning("Skipping post %s (crossposts are disabled). Crosspost from %s", post["id"], c_parent)
            self.tui.files.stats.skipped += 1
            return

        deleted_post = bool(post.get("_meta", {}).get("removal_type"))
        sleep = aio.periodic_sleep(10)

        for url in unique(
            map(
                _transform_media_url,
                itertools.chain(
                    _extract_gallery_urls(post, conf),
                    _extract_media_urls(post, conf),
                    _extract_preview_urls(post, conf),
                    _extract_content_urls(post, conf),
                ),
            )
        ):
            if url.host == self.PRIMARY_URL.host:
                match url.parts[1:]:
                    case ["gallery", media_id] if media_id == post["id"]:
                        continue
                    case ["r" | "u" | "user" | "gallery", *_]:
                        self.log.warning("Skipping nested reddit URL found in post %s: %s", post["id"], url)
                        continue
                    case _:
                        pass

            new_item = scrape_item.create_child(url)
            if url.host == RedditImagesCrawler.PRIMARY_URL.host and not url.suffix:
                if deleted_post:
                    await self.raise_exc(new_item, 410)
                    continue

                self.log.warning("Unable to identify extension for %s. Download may fail", url.name)

            self.handle_embed(new_item)
            scrape_item.add_children()
            await sleep()

    _post_task = auto_task_id(error_handling_wrapper(_post))

    @error_handling_wrapper
    async def submission(self, scrape_item: ScrapeItem, post_id: str) -> None:
        post = await self.api.post(post_id)
        await self._post(scrape_item, post)


def _transform_media_url(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    for cls in (RedditImagesCrawler, RedditVideoCrawler):
        for domain in cls.SUPPORTED_DOMAINS:
            if is_within_domain(domain, url.host):
                return cls.transform_url(url)
    return url


def _extract_gallery_urls(post: Submission, _config: RedditConfig) -> Generator[AbsoluteHttpURL]:
    gallery = post.get("gallery_data")
    if not gallery:
        return

    metadata = post.get("media_metadata") or {}
    for item in gallery["items"]:
        media_id = item["media_id"]
        meta = metadata[media_id]
        if meta.get("status", "valid") != "valid":
            RedditCrawler.get_logger().warning("Invalid image (deleted?)\n%s\n%s", item, meta)

        ext = None
        src = meta.get("s") or {}

        if src_url := src.get("u"):
            ext = parse_http_url(src_url).suffix

        if not ext and (mime := meta.get("m")):
            ext = _guess_ext(mime)

        slug = f"{media_id}{ext}" if ext else media_id
        yield RedditImagesCrawler.PRIMARY_URL / slug
        for url in (src.get("mp4"), src.get("gif")):
            if url:
                yield parse_http_url(url)


def _extract_media_urls(post: Submission, _config: RedditConfig) -> Generator[AbsoluteHttpURL]:
    media = post.get("media") or post.get("secure_media")
    if not media:
        return

    if video := media.get("reddit_video"):
        yield parse_http_url(video["dash_url"])

    if oembed := media.get("oembed"):
        if url := oembed.get("thumbnail_url"):
            yield parse_http_url(url)
        if html := oembed.get("html"):
            for src in css.iselect(css.soup(html, parse_only="iframe"), "iframe", "src"):
                yield parse_http_url(src)


def _extract_content_urls(post: Submission, config: RedditConfig) -> Generator[AbsoluteHttpURL]:
    yield parse_http_url(post.get("url_overridden_by_dest") or post["url"])
    if config.content_urls and (content := post.get("selftext_html")):
        soup = css.soup(content, parse_only="a")
        yield from map(parse_http_url, css.iselect(soup, "a[href]", "href"))


def _extract_preview_urls(post: Submission, config: RedditConfig) -> Generator[AbsoluteHttpURL]:
    preview = post.get("preview")
    if not preview:
        return

    try:
        preview_url = preview["images"][0]["source"]["url"]
    except LookupError:
        pass
    else:
        if preview:
            yield parse_http_url(preview_url)

    if (video := preview.get("reddit_video_preview")) and config.video_previews:
        yield parse_http_url(video["dash_url"])


def _guess_ext(mime: str) -> str | None:
    if mime == "image/jpg":
        return ".jpg"
    if mime == "image/jpeg":
        return ".jpeg"
    return mimetypes.guess_extension(mime)
