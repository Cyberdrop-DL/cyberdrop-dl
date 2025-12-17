from __future__ import annotations

import dataclasses
import importlib.util
import re
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, NotRequired
from unittest import mock

import pytest
from pydantic import TypeAdapter
from typing_extensions import TypedDict

from cyberdrop_dl.data_structures import AbsoluteHttpURL
from cyberdrop_dl.data_structures.url_objects import MediaItem, ScrapeItem
from cyberdrop_dl.scraper.scrape_mapper import ScrapeMapper
from cyberdrop_dl.utils.utilities import parse_url

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import Crawler
    from cyberdrop_dl.managers.manager import Manager


def _crawler_mock(func: str = "handle_media_item") -> mock._patch[mock.AsyncMock]:
    return mock.patch(f"cyberdrop_dl.crawlers.crawler.Crawler.{func}", new_callable=mock.AsyncMock)


class Result(TypedDict):
    # Simplified version of media_item
    url: str
    filename: NotRequired[str]
    debrid_link: NotRequired[str | None]
    original_filename: NotRequired[str]
    referer: NotRequired[str]
    album_id: NotRequired[str | None]
    datetime: NotRequired[int | None]
    download_folder: NotRequired[str]


@dataclasses.dataclass(slots=True)
class Config:
    skip: str | bool = False
    total: int | None = None


_default_config = Config()


class CrawlerTestCase(NamedTuple):
    domain: str
    input_url: str
    results: list[Result]
    # TODO: deprecated total, move to config
    total: Sequence[int] | int | None = None
    config: Config = _default_config


_TEST_CASE_ADAPTER = TypeAdapter(CrawlerTestCase)
_TEST_DATA: dict[str, list[tuple[str, list[Result], int, Config]]] = {}


def _load_test_cases(path: Path) -> None:
    module_spec = importlib.util.spec_from_file_location(path.stem, path)
    assert module_spec and module_spec.loader
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    _TEST_DATA[module.DOMAIN] = module.TEST_CASES


def _load_test_data() -> None:
    if _TEST_DATA:
        return
    for file in (Path(__file__).parent / "test_cases").iterdir():
        if not file.name.startswith("_") and file.suffix == ".py":
            _load_test_cases(file)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    _load_test_data()
    if "crawler_test_case" in metafunc.fixturenames:
        valid_domains = sorted(_TEST_DATA)
        domains_to_tests: list[str] = getattr(metafunc.config, "test_crawlers_domains", [])
        for domain in domains_to_tests:
            assert domain in valid_domains, f"{domain = } is not a valid or has not tests defined"

        all_test_cases: list[CrawlerTestCase] = []
        for domain, test_cases in _TEST_DATA.items():
            if domain in domains_to_tests:
                all_test_cases.extend(CrawlerTestCase(domain, *case) for case in test_cases)
        metafunc.parametrize("crawler_test_case", all_test_cases, ids=lambda x: f"{x.domain} - {x.input_url}")


@pytest.mark.crawler_test_case
async def test_crawler(running_manager: Manager, crawler_test_case: CrawlerTestCase) -> None:
    # Check that this is a valid test case with pydantic
    test_case = _TEST_CASE_ADAPTER.validate_python(crawler_test_case)
    if skip := test_case.config.skip:
        pytest.skip(skip) if isinstance(skip, str) else pytest.skip()

    with _crawler_mock() as func:
        async with ScrapeMapper(running_manager) as scrape_mapper:
            await scrape_mapper.run()
            crawler = next(
                (crawler for crawler in scrape_mapper.existing_crawlers.values() if crawler.DOMAIN == test_case.domain),
                None,
            )
            assert crawler, f"{test_case.domain} is not a valid crawler domain. Test case is invalid"
            await crawler.startup()
            item = ScrapeItem(url=crawler.parse_url(test_case.input_url))
            await crawler.run(item)

    results: list[MediaItem] = sorted((call.args[0] for call in func.call_args_list), key=lambda x: str(x.url))
    total = test_case.total or len(test_case.results)
    _assert_n_results(test_case, len(results))
    if total:
        func.assert_awaited()
        _validate_results(crawler, test_case, results)


def _assert_n_results(test_case: CrawlerTestCase, n_results: int) -> None:
    total = test_case.total or len(test_case.results)
    if isinstance(total, Sequence):
        assert n_results in total
    else:
        assert total == n_results


def _validate_results(crawler: Crawler, test_case: CrawlerTestCase, results: list[MediaItem]) -> None:
    expected_results = sorted(test_case.results, key=lambda x: x["url"])
    origin = getattr(crawler, "PRIMARY_URL", AbsoluteHttpURL("https://google.com"))
    for index, (expected, media_item) in enumerate(zip(expected_results, results, strict=False), 1):
        for attr_name, expected_value in expected.items():
            result_value = getattr(media_item, attr_name)
            if isinstance(expected_value, str):
                if expected_value.startswith("http"):
                    expected_value = crawler.parse_url(expected_value, origin)
                elif expected_value == "ANY":
                    expected_value = mock.ANY
                elif expected_value.startswith("re:"):
                    expected_value = expected_value.removeprefix("re:")
                    assert _re_search(expected_value, str(result_value)), (
                        f"{result_value = } does not match {expected_value}"
                    )
                    continue

            assert expected_value == result_value, f"{attr_name} for result#{index} is different"


def _re_search(expected_value: str, result_value: str) -> re.Match[str] | None:
    return re.search(expected_value, str(result_value)) or re.search(re.escape(expected_value), str(result_value))


@pytest.mark.parametrize(
    "url, filename",
    [
        (
            "https://techdigitalspace.com/wp-content/uploads/2025/11/Valve-Steam-Machine-2.jpg",
            "Valve-Steam-Machine-2.jpg",
        ),
        (
            "https://simpcity.su/attachments/273974549_106860831858568_7219174579013873561_n-jpg.40743",
            "273974549_106860831858568_7219174579013873561_n.jpg",
        ),
        (
            "https://storage.googleapis.com/gweb-uniblog-publish-prod/images/Android_14-Hero_image-P8P.width-1300.png",
            "Android_14-Hero_image-P8P.width-1300.png",
        ),
    ],
)
async def test_direct_http_crawler(running_manager: Manager, url: str, filename: str) -> None:
    test_case = CrawlerTestCase(domain="no_crawler", input_url=url, results=[{"url": url, "filename": filename}])

    with _crawler_mock() as func:
        async with ScrapeMapper(running_manager) as scrape_mapper:
            crawler = scrape_mapper.direct_crawler
            await scrape_mapper.run()
            item = ScrapeItem(url=parse_url(test_case.input_url))
            await crawler.fetch(item)

    results: list[MediaItem] = sorted((call.args[0] for call in func.call_args_list), key=lambda x: str(x.url))
    func.assert_awaited()
    _validate_results(crawler, test_case, results)
