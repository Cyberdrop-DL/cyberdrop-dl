from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import datetime
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self, TypeVar

from cyberdrop_dl import aio, plugins, storage
from cyberdrop_dl.clients.jdownloader import JDownloader
from cyberdrop_dl.constants import BlockedDomains
from cyberdrop_dl.crawlers import create_crawlers
from cyberdrop_dl.crawlers._chevereto import CheveretoCrawler
from cyberdrop_dl.crawlers.discourse import DiscourseCrawler
from cyberdrop_dl.crawlers.http_direct import DirectHttpFile
from cyberdrop_dl.crawlers.realdebrid import RealDebridCrawler
from cyberdrop_dl.crawlers.wordpress import WordPressHTMLCrawler, WordPressMediaCrawler
from cyberdrop_dl.exceptions import JDownloaderError, NoExtensionError
from cyberdrop_dl.logs import log_spacer
from cyberdrop_dl.progress.scraping import ScrapingUI
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import filepath, get_download_path, remove_trailing_slash

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Coroutine, Generator, Iterable, Iterator, Sequence

    import aiosqlite

    from cyberdrop_dl.config._global import GenericCrawlerInstances
    from cyberdrop_dl.crawlers.crawler import Crawler
    from cyberdrop_dl.managers.manager import Manager

    _T = TypeVar("_T")
    _CrawlerT = TypeVar("_CrawlerT", bound=Crawler)

logger = logging.getLogger(__name__)


REGEX_LINKS = re.compile(r"(?:http.*?)(?=($|\n|\r\n|\r|\s|\"|\[/URL]|']\[|]\[|\[/img]))")


def _filter_by_date(scrape_item: ScrapeItem, before: datetime.date | None, after: datetime.date | None) -> bool:
    skip = False
    item_date = scrape_item.completed_at or scrape_item.created_at
    if not item_date:
        return False
    date = datetime.datetime.fromtimestamp(item_date).date()
    if (after and date < after) or (before and date > before):
        skip = True

    return skip


def _filter_by_domain(scrape_item: ScrapeItem, domain_list: Sequence[str]) -> bool:
    return any(domain in scrape_item.url.host for domain in domain_list)


@dataclasses.dataclass(slots=True, eq=False)
class CrawlerFactory:
    manager: Manager
    _instances: dict[type[Crawler], Crawler] = dataclasses.field(default_factory=dict)

    def __getitem__(self, obj: type[_CrawlerT]) -> _CrawlerT:
        instance = self.get(obj)
        if instance is None:
            instance = self._instances[obj] = obj(self.manager)
        return instance

    def __contains__(self, obj: type[_CrawlerT]) -> bool:
        return obj in self._instances

    def get(self, obj: type[_CrawlerT]) -> _CrawlerT | None:
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
        if item.parent_title:
            self.groups.append(item.parent_title)


@dataclasses.dataclass(slots=True)
class TaskGroups:
    scrape: asyncio.TaskGroup
    downloads: asyncio.TaskGroup


@dataclasses.dataclass(slots=True)
class ScrapeMapper:
    """This class maps links to their respective handlers, or JDownloader if they are unsupported."""

    manager: Manager
    crawlers: dict[str, type[Crawler]] = dataclasses.field(init=False, default_factory=dict)

    _direct_http: DirectHttpFile = dataclasses.field(init=False)
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
        return sum(f.waiting_items for f in self._factory)

    def _download_queue(self):
        total = sum(f.downloader.waiting_items for f in self._factory)
        self.tui.files.stats.queued = total
        return total

    def __post_init__(self) -> None:
        self._direct_http = DirectHttpFile(self.manager)
        self._jdownloader = JDownloader.from_manager(self.manager)
        self._real_debrid = RealDebridCrawler(self.manager)
        self._factory = CrawlerFactory(self.manager)
        self.tui.scrape.get_queue = self._scrape_queue
        self.tui.downloads.get_queue = self._download_queue

    def create_task(self, coro: Coroutine[Any, Any, _T]) -> None:
        _ = self._task_groups.scrape.create_task(coro)

    def create_download_task(self, coro: Coroutine[Any, Any, _T]) -> None:
        _ = self._task_groups.downloads.create_task(coro)

    def _init_crawlers(self) -> None:

        self.crawlers.update(get_crawlers_mapping())

        for crawler in _create_generic_crawlers(self.manager.config.global_settings.generic_crawlers_instances):
            register_crawler(self.crawlers, crawler, from_user=True)

        _disable_crawlers_by_config(self.crawlers, *self.manager.config.global_settings.general.disable_crawlers)

        plugins.load(self.manager)

    @contextlib.asynccontextmanager
    async def __call__(self) -> AsyncGenerator[Self]:
        assert not self._done.is_set()
        _ = filepath.MAX_FILE_LEN.set(self.manager.config.global_settings.general.max_file_name_length)
        _ = filepath.MAX_FOLDER_LEN.set(self.manager.config.global_settings.general.max_folder_name_length)

        await self.manager.client_manager.load_cookie_files()
        self.tui.mode = self.manager.cli_args.ui
        ## IMPORTANT: Order of each context matters!
        with self.tui():
            async with (
                self.manager.client_manager,
                storage.monitor(self.manager.config.global_settings.general.required_free_space),
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
        self._direct_http.__init_downloader__()

        item_limit = 0
        if self.manager.cli_args.retry_any and self.manager.cli_args.max_items_retry:
            item_limit = self.manager.cli_args.max_items_retry

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

            async for item in items:
                item.children_limits = self.manager.config.settings.download_options.maximum_number_of_children
                if self._should_scrape(item):
                    if item_limit and stats.count >= item_limit:
                        break
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
            return

        except (NoExtensionError, ValueError):
            pass

        if self._jdownloader.is_enabled_for(scrape_item.url):
            logger.info(f"Sending unsupported URL to JDownloader: {scrape_item.url}")

            download_folder = get_download_path(self.manager, scrape_item, "jdownloader")
            relative_download_dir = download_folder.relative_to(self.manager.config.settings.files.download_folder)
            try:
                await self._jdownloader.send(
                    scrape_item.url,
                    scrape_item.parent_title,
                    relative_download_dir,
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

        before = self.manager.cli_args.completed_before
        after = self.manager.cli_args.completed_after

        if _filter_by_date(scrape_item, before, after):
            logger.info(f"Skipping {scrape_item.url} as it is outside of the desired date range")
            return False

        skip_hosts = self.manager.config.settings.ignore_options.skip_hosts
        if skip_hosts and _filter_by_domain(scrape_item, skip_hosts):
            logger.info(f"Skipping {scrape_item.url} by skip_hosts config")
            return False

        only_hosts = self.manager.config.settings.ignore_options.only_hosts
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
            return

        crawler = next((crawler for crawler in self.crawlers.values() if crawler.DOMAIN == domain), None)
        if not crawler or crawler.disabled:
            return

        crawler.disabled = True
        self._crawlers_disabled_at_runtime.add(domain)
        if instance := self._factory.get(crawler):
            instance.disabled = True
        return crawler


def _source(manager: Manager) -> tuple[str, AsyncGenerator[ScrapeItem]]:
    cli_args = manager.cli_args

    if cli_args.retry_failed:
        return "--retry-failed", load_failed_links(manager)
    if cli_args.retry_all:
        return "--retry-all", load_all_links(manager)
    if cli_args.retry_maintenance:
        return "--retry-maintenance", load_all_bunkr_failed_links_via_hash(manager)
    if cli_args.links:
        return "--links (CLI args)", _load_cli_links(cli_args.links)

    return str(manager.config.settings.files.input_file), _load_urls_from_file(manager.config.settings.files.input_file)


async def _load_urls_from_file(file: Path) -> AsyncGenerator[ScrapeItem]:
    async for group_name, urls in _parse_input_file_groups(file):
        for url in urls:
            item = ScrapeItem(url=url)
            if group_name:
                item.add_to_parent_title(group_name)
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
        yield ScrapeItem(url=url)


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
        except Exception as e:
            logger.error(f"Unable to parse URL from input file: {link} {e:!r}")


def _create_item_from_row(row: aiosqlite.Row) -> ScrapeItem:
    referer: str = row["referer"]
    url = AbsoluteHttpURL(referer, encoded="%" in referer)
    item = ScrapeItem(url=url, retry_path=Path(row["download_path"]), part_of_album=True)
    if completed_at := row["completed_at"]:
        item.completed_at = int(datetime.datetime.fromisoformat(completed_at).timestamp())
    if created_at := row["created_at"]:
        item.created_at = int(datetime.datetime.fromisoformat(created_at).timestamp())
    return item


def get_crawlers_mapping(include_generics: bool = False) -> dict[str, type[Crawler]]:
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
            else:
                logger.info("Successfully mapped %s to crawler %s", crawler.PRIMARY_URL, crawler.NAME)

        elif other:
            if domain in crawlers_map:
                logger.warning("%s from %s already registered by %s", domain, crawler.NAME, other)

        crawlers_map[domain] = crawler


def _create_generic_crawlers(generics_config: GenericCrawlerInstances) -> Generator[type[Crawler]]:

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


def _best_match(current_map: dict[str, _T], domain: str) -> _T | None:
    if found := current_map.get(domain):
        return found

    try:
        best_match = max((host for host in current_map if host in domain), key=len)
    except (ValueError, TypeError):
        return
    else:
        current_map[domain] = found = current_map[best_match]
        return found


async def load_failed_links(manager: Manager) -> AsyncGenerator[ScrapeItem]:
    async for rows in manager.database.history.get_failed_items():
        for row in rows:
            yield _create_item_from_row(row)


async def load_all_links(manager: Manager) -> AsyncGenerator[ScrapeItem]:
    after = manager.cli_args.completed_after or datetime.date.min
    before = manager.cli_args.completed_before or datetime.date.today()
    async for rows in manager.database.history.get_all_items(after, before):
        for row in rows:
            yield _create_item_from_row(row)


async def load_all_bunkr_failed_links_via_hash(manager: Manager) -> AsyncGenerator[ScrapeItem]:
    async for rows in manager.database.history.get_all_bunkr_failed():
        for row in rows:
            yield _create_item_from_row(row)
