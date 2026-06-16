from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import re
import time
from typing import TYPE_CHECKING, Any, Literal, Self

from pydantic.types import ByteSize

from cyberdrop_dl import aio, env, filepath, storage
from cyberdrop_dl.clients.jdownloader import JDownloader
from cyberdrop_dl.constants import BlockedDomains
from cyberdrop_dl.crawlers import create_crawlers
from cyberdrop_dl.crawlers._chevereto import CheveretoCrawler
from cyberdrop_dl.crawlers.crawler import ALLOW_NO_EXT
from cyberdrop_dl.crawlers.discourse import DiscourseCrawler
from cyberdrop_dl.crawlers.http_direct import DirectHttpFileCrawler
from cyberdrop_dl.crawlers.realdebrid import RealDebridCrawler
from cyberdrop_dl.crawlers.wordpress import WordPressHTMLCrawler, WordPressMediaCrawler
from cyberdrop_dl.downloader.hls import CONCURRENT_SEGMENTS
from cyberdrop_dl.exceptions import JDownloaderError, NoExtensionError
from cyberdrop_dl.logs import log_spacer
from cyberdrop_dl.progress.scraping import ScrapingUI
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import remove_trailing_slash

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Coroutine, Generator, Iterable, Iterator, Sequence
    from pathlib import Path

    from cyberdrop_dl.config.settings import GenericCrawlers
    from cyberdrop_dl.crawlers.crawler import Crawler
    from cyberdrop_dl.manager import Manager


logger = logging.getLogger(__name__)


REGEX_LINKS = re.compile(r"(?:http.*?)(?=($|\n|\r\n|\r|\s|\"|\[/URL]|']\[|]\[|\[/img]))")


def _filter_by_domain(scrape_item: ScrapeItem, domain_list: Sequence[str]) -> bool:
    return any(domain in scrape_item.url.host for domain in domain_list)


@dataclasses.dataclass(slots=True, eq=False)
class CrawlerFactory:
    manager: Manager
    _instances: dict[type[Crawler], Crawler] = dataclasses.field(default_factory=dict)

    def __getitem__[CrawlerT: Crawler](self, obj: type[CrawlerT]) -> CrawlerT:
        instance = self.get(obj)
        if instance is None:
            instance = self._instances[obj] = obj(self.manager)
        return instance

    def __contains__[CrawlerT: Crawler](self, obj: type[CrawlerT]) -> bool:
        return obj in self._instances

    def get[CrawlerT: Crawler](self, obj: type[CrawlerT]) -> CrawlerT | None:
        return self._instances.get(obj)  # pyright: ignore[reportReturnType]

    def __iter__(self) -> Iterator[Crawler]:
        return iter(self._instances.values())


@dataclasses.dataclass(slots=True)
class ScrapeStats:
    source: Path | str
    count: int = dataclasses.field(init=False, default=0)
    groups: list[str] = dataclasses.field(init=False, default_factory=list)
    url_count: dict[str, int] = dataclasses.field(init=False, default_factory=dict)
    start_time: float = dataclasses.field(init=False, default_factory=time.monotonic)

    @property
    def unique_groups(self) -> list[str]:
        return list(dict.fromkeys(self.groups))

    @property
    def domain_stats(self) -> dict[str, int]:
        return dict(sorted(self.url_count.items(), key=lambda x: x[1]))

    def update(self, item: ScrapeItem) -> None:
        self.count += 1
        if item.folders:
            self.groups.append("/".join(item.folders))


@dataclasses.dataclass(slots=True)
class TaskGroups:
    scrape: asyncio.TaskGroup
    downloads: asyncio.TaskGroup


@dataclasses.dataclass(slots=True)
class ScrapeMapper:
    """This class maps links to their respective handlers, or JDownloader if they are unsupported."""

    manager: Manager
    crawlers: dict[str, type[Crawler]] = dataclasses.field(init=False, default_factory=dict)

    _direct_http: DirectHttpFileCrawler = dataclasses.field(init=False)
    _jdownloader: JDownloader = dataclasses.field(init=False)
    _real_debrid: RealDebridCrawler = dataclasses.field(init=False)
    _task_groups: TaskGroups = dataclasses.field(
        init=False, default_factory=lambda: TaskGroups(asyncio.TaskGroup(), asyncio.TaskGroup())
    )
    _seen_urls: set[AbsoluteHttpURL] = dataclasses.field(init=False, default_factory=set)
    _crawlers_disabled_at_runtime: set[str] = dataclasses.field(init=False, default_factory=set)
    _factory: CrawlerFactory = dataclasses.field(init=False)
    tui: ScrapingUI = dataclasses.field(init=False, default_factory=ScrapingUI)
    _done: asyncio.Event = dataclasses.field(init=False, default_factory=asyncio.Event)

    def _scrape_queue(self) -> int:
        return sum(crawler.waiting_items for crawler in self._factory)

    def _download_queue(self) -> int:
        total = sum(crawler.downloader.waiting_items for crawler in self._factory)
        self.tui.files.stats.queued = total
        return total

    def __post_init__(self) -> None:
        self._direct_http = DirectHttpFileCrawler(self.manager)
        self._jdownloader = JDownloader.from_config(self.manager.config)
        self._real_debrid = RealDebridCrawler(self.manager)
        self._factory = CrawlerFactory(self.manager)
        self.tui.scrape.get_queue = self._scrape_queue
        self.tui.downloads.get_queue = self._download_queue

    def create_task[T](self, coro: Coroutine[Any, Any, T]) -> None:
        # skip 1 loop iteration to give priority to download tasks
        async def lazy() -> T:
            await asyncio.sleep(0)
            return await coro

        _ = self._task_groups.scrape.create_task(lazy())

    def create_download_task[T](self, coro: Coroutine[Any, Any, T]) -> None:
        _ = self._task_groups.downloads.create_task(coro)

    def _init_crawlers(self) -> None:

        self.crawlers.update(get_crawlers_mapping())

        for crawler in _create_generic_crawlers(self.manager.config.generic_crawlers):
            register_crawler(self.crawlers, crawler, from_user=True)

        _disable_crawlers_by_config(self.crawlers, *self.manager.config.crawlers.disabled)

    @contextlib.asynccontextmanager
    async def __call__(self) -> AsyncGenerator[Self]:
        assert not self._done.is_set()
        config = self.manager.config
        _ = filepath.MAX_FILE_LEN.set(config.max_file_name_length)
        _ = filepath.MAX_FOLDER_LEN.set(config.max_folder_name_length)
        _ = CONCURRENT_SEGMENTS.set(config.downloads.concurrent_segments)
        _ = ALLOW_NO_EXT.set(config.filters.allow_files_with_no_extension)
        if config.ui.portrait:
            env.FORCE_PORTRAIT_MODE = True

        config.download_folder.mkdir(parents=True, exist_ok=True)
        if config.sort.enabled:
            config.sort.output_folder.mkdir(parents=True, exist_ok=True)

        logger.debug(
            "Using %s as chunk size", ByteSize(self.manager.download_client.chunk_size).human_readable(decimal=True)
        )
        await self.manager.http_client.load_cookie_files(await self.manager.get_cookie_files())
        self.tui.mode = self.manager.config.ui.mode
        ## IMPORTANT: Order of each context matters!
        with self.tui():
            async with (
                self.manager.http_client,
                storage.monitor(config.min_free_space),
                self.manager.logs.task_group,
                self._task_groups.downloads,
            ):
                try:
                    async with self._task_groups.scrape:
                        self.manager.scrape_mapper = self

                        yield self

                finally:
                    # The done event signals that all scraping is done, but there may still be downloads pending
                    self._done.set()

    async def run(self) -> ScrapeStats:
        self._init_crawlers()
        try:
            await self._jdownloader.connect()
        except JDownloaderError:
            logger.exception("Failed to connect to jDownloader")

        await self._real_debrid.__async_init__()
        await self._direct_http.__async_post_init__()

        source_name, source = _source(self.manager)
        async with contextlib.aclosing(source) as items:
            stats = ScrapeStats(source_name)

            async def wait_until_scrape_is_done() -> None:
                _ = await self._done.wait()
                self.tui.hide_scrape_panel()
                stats.url_count.update(
                    (crawler.DOMAIN, count) for crawler in self._factory if (count := len(crawler._scraped_items))
                )

            self.create_download_task(wait_until_scrape_is_done())

            children_limits = tuple(self.manager.config.max_children)
            async for item in items:
                item.children_limits = children_limits
                item.download_folder = self.manager.config.download_folder
                if self._should_scrape(item):
                    stats.update(item)
                    self.create_task(self._send_to_crawler(item))

        if not stats.count:
            logger.warning("No valid links found")

        return stats

    async def send_to_crawler(self, scrape_item: ScrapeItem) -> None:
        if self._should_scrape(scrape_item):
            await self._send_to_crawler(scrape_item)

    async def _send_to_crawler(self, scrape_item: ScrapeItem) -> None:
        scrape_item.url = remove_trailing_slash(scrape_item.url)
        if cls := _best_match(self.crawlers, scrape_item.url.host):
            crawler = self._factory[cls]
            await crawler.__async_init__()
            self.create_task(crawler.run(scrape_item))
            return

        if not self._real_debrid.disabled and self._real_debrid.api.is_supported(scrape_item.url):
            logger.info(f"Using RealDebrid for unsupported URL: {scrape_item.url}")
            self.create_task(self._real_debrid.run(scrape_item))
            return

        try:
            await self._direct_http.fetch(scrape_item)
        except (NoExtensionError, ValueError):
            pass
        else:
            return

        if self._jdownloader.is_enabled_for(scrape_item.url):
            logger.info(f"Sending unsupported URL to JDownloader: {scrape_item.url}")

            try:
                await self._jdownloader.send(
                    scrape_item.url,
                    scrape_item.path.as_posix(),
                    scrape_item.path,
                )

            except JDownloaderError as e:
                logger.error(f"Failed to send {scrape_item.url} to JDownloader\n{e.message}")
                self.manager.logs.write_unsupported(
                    scrape_item.url,
                    scrape_item.parents[0] if scrape_item.parents else None,
                )
                success = False
            else:
                success = True

            self.tui.scrape_errors.add_unsupported(sent_to_jdownloader=success)
            return

        logger.warning(f"Unsupported URL: {scrape_item.url}")
        self.manager.logs.write_unsupported(scrape_item.url, scrape_item.parents[0] if scrape_item.parents else None)
        self.tui.scrape_errors.add_unsupported()

    def _should_scrape(self, scrape_item: ScrapeItem) -> bool:
        if scrape_item.url in self._seen_urls:
            return False

        self._seen_urls.add(scrape_item.url)

        if (
            _filter_by_domain(scrape_item, BlockedDomains.partial_match)
            or scrape_item.url.host in BlockedDomains.exact_match
        ):
            logger.info(f"Skipping {scrape_item.url} as it is a blocked domain")
            return False

        skip_hosts = self.manager.config.filters.skip_hosts
        if skip_hosts and _filter_by_domain(scrape_item, skip_hosts):
            logger.info(f"Skipping {scrape_item.url} by skip_hosts config")
            return False

        only_hosts = self.manager.config.filters.only_hosts
        if only_hosts and not _filter_by_domain(scrape_item, only_hosts):
            logger.info(f"Skipping {scrape_item.url} by only_hosts config")
            return False

        return True

    def disable_crawler(self, domain: str) -> type[Crawler] | None:
        """Disables a crawler at runtime, after the scrape mapper is already running.

        It does not remove the crawler from the crawlers map, it just sets it as `disabled"`

        This has the effect to silently ignore any URL that maps to that crawler, without any "unsupported" or "errors" log messages

        `domain` must match _exactly_, AKA: it must be the value of `crawler.DOMAIN`

        Returns the crawler instance that was disabled (if Any)

        """

        if domain in self._crawlers_disabled_at_runtime:
            return None

        crawler = next((crawler for crawler in self.crawlers.values() if domain == crawler.DOMAIN), None)
        if not crawler or crawler.disabled:
            return None

        crawler.disabled = True
        self._crawlers_disabled_at_runtime.add(domain)
        if instance := self._factory.get(crawler):
            instance.disabled = True
        return crawler


def _source(manager: Manager) -> tuple[str, AsyncGenerator[ScrapeItem]]:
    cli_args = manager.cli_args
    if cli_args.links:
        return "--links (CLI args)", _load_cli_links(cli_args.links)

    return str(manager.input_file), _load_urls_from_file(manager.input_file)


async def _load_urls_from_file(file: Path) -> AsyncGenerator[ScrapeItem]:
    async for group_name, urls in _parse_input_file_groups(file):
        for url in urls:
            item = ScrapeItem.from_url(url)
            if group_name:
                item.append_folders(group_name)
                item.part_of_album = True
            yield item


async def _parse_input_file_groups(input_file: Path) -> AsyncGenerator[tuple[str, list[AbsoluteHttpURL]]]:
    if not await aio.is_file(input_file):
        yield ("", [])
        return

    block_quote = False
    current_group_name = ""
    async with aio.open(input_file, encoding="utf8") as f:
        async for line in f:
            if line.startswith(("---", "===")):  # New group begins here
                current_group_name = line.replace("---", "").replace("===", "").strip()

            if current_group_name:
                yield (current_group_name, list(_regex_links(line)))
                continue

            block_quote = not block_quote if line == "#\n" else block_quote
            if not block_quote:
                yield ("", list(_regex_links(line)))


async def _load_cli_links(links: Iterable[AbsoluteHttpURL]) -> AsyncGenerator[ScrapeItem]:
    for url in links:
        yield ScrapeItem.from_url(url)


def _regex_links(line: str) -> Generator[AbsoluteHttpURL]:
    """Regex grab the links from the URLs.txt file.

    This allows code blocks or full paragraphs to be copy and pasted into the URLs.txt.
    """

    line = line.strip()
    if line.startswith("#"):
        return

    http_urls = (url.group().replace(".md.", ".") for url in re.finditer(REGEX_LINKS, line))
    for link in http_urls:
        try:
            encoded = "%" in link
            yield AbsoluteHttpURL(link, encoded=encoded)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Unable to parse URL from input file: {link} {e:!r}")


def get_crawlers_mapping(*, include_generics: bool = False) -> dict[str, type[Crawler]]:
    from cyberdrop_dl.crawlers.crawler import Registry

    Registry.import_all()

    crawlers_map: dict[str, type[Crawler]] = {}

    crawlers = Registry.concrete | Registry.generic if include_generics else Registry.concrete

    for crawler in sorted(crawlers, key=lambda c: c.NAME):
        register_crawler(crawlers_map, crawler)

    copy = crawlers_map.copy()
    crawlers_map.clear()
    crawlers_map.update(sorted(copy.items()))
    return crawlers_map


def register_crawler(
    crawlers_map: dict[str, type[Crawler]],
    crawler: type[Crawler],
    *,
    from_user: bool | Literal["raise"] = False,
) -> None:

    for domain in crawler.SCRAPE_MAPPER_KEYS:
        other = crawlers_map.get(domain)
        if from_user:
            if not other and (match := _best_match(crawlers_map, crawler.PRIMARY_URL.host)):
                other = match
            if other:
                msg = (
                    f"Unable to assign {crawler.PRIMARY_URL} to generic crawler {crawler.NAME}. "
                    f"URL conflicts with URL format of builtin crawler {other.NAME}. "
                    "URL will be ignored"
                )
                if from_user == "raise":
                    raise ValueError(msg)
                logger.error(msg)
                continue
            logger.info("Successfully mapped %s to crawler %s", crawler.PRIMARY_URL, crawler.NAME)

        elif other:
            if domain in crawlers_map:
                logger.warning("%s from %s already registered by %s", domain, crawler.NAME, other)

        crawlers_map[domain] = crawler


def _create_generic_crawlers(generics_config: GenericCrawlers) -> Generator[type[Crawler]]:

    for domains, cls in (
        (generics_config.wordpress_html, WordPressHTMLCrawler),
        (generics_config.wordpress_media, WordPressMediaCrawler),
        (generics_config.discourse, DiscourseCrawler),
        (generics_config.chevereto, CheveretoCrawler),
    ):
        if domains:
            yield from create_crawlers(domains, cls)


def _disable_crawlers_by_config(current_crawlers: dict[str, type[Crawler]], *crawlers_to_disable: str) -> None:
    if not crawlers_to_disable:
        return

    crawlers_to_disable = tuple(sorted({name.casefold() for name in crawlers_to_disable}))

    new_crawlers_mapping = {
        domain: crawler
        for domain, crawler in current_crawlers.items()
        if crawler.INFO.site.casefold() not in crawlers_to_disable
    }

    disabled_crawlers = set(current_crawlers.values()) - set(new_crawlers_mapping.values())

    if len(disabled_crawlers) != len(crawlers_to_disable):
        msg = (
            f"{len(crawlers_to_disable)} Crawler names where provided to disable"
            f", but only {len(disabled_crawlers)} {'is' if len(disabled_crawlers) == 1 else 'are'} a valid crawler's name."
        )
        logger.warning(msg)

    if disabled_crawlers:
        current_crawlers.clear()
        current_crawlers.update(new_crawlers_mapping)
        crawlers_info = "\n".join(
            str({info.site: info.supported_domains}) for info in sorted(c.INFO for c in disabled_crawlers)
        )
        logger.info(f"Crawlers disabled by config: \n{crawlers_info}")

    log_spacer()


def _best_match[T](current_map: dict[str, T], domain: str) -> T | None:
    if found := current_map.get(domain):
        return found

    try:
        best_match = max((host for host in current_map if host in domain), key=len)
    except (ValueError, TypeError):
        return None
    else:
        current_map[domain] = found = current_map[best_match]
        return found
