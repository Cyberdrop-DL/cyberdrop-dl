from __future__ import annotations

import dataclasses
import runpy
from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from collections.abc import Sequence


class Result(TypedDict):
    # Simplified version of media_item
    url: str
    filename: NotRequired[str | type]
    debrid_link: NotRequired[str | type | None]
    original_filename: NotRequired[str | type]
    referer: NotRequired[str | type]
    album_id: NotRequired[str | type | None]
    uploaded_at: NotRequired[int | type | None]
    download_folder: NotRequired[str | type]


@dataclasses.dataclass(slots=True)
class CrawlerTestCase:
    domain: str
    url: str
    results: list[Result]
    description: str | None = None
    fail: bool | str | int = False
    xfail: str | None = None
    skip: str | bool = False
    count: Sequence[int] | int | None = None
    options: list[str] | None = None
    log: str | None = None

    @property
    def test_id(self) -> str:
        return f"{self.domain} - {self.url}"


type TestData = dict[str, list[dict[str, Any]]]

_TEST_CASE_ADAPTER = TypeAdapter(CrawlerTestCase)


def load_cases() -> TestData:
    test_data: TestData = {}
    for file in (Path(__file__).parent).iterdir():
        if not file.name.startswith("_") and file.suffix == ".py":
            module_globals = runpy.run_path(str(file), run_name=file.stem)
            if (domain := module_globals["DOMAIN"]) in test_data:
                raise RuntimeError(f"Multiple tests files for {domain}")

            test_data[domain] = module_globals["TEST_CASES"]

    return test_data


def parse_cases(data: TestData) -> list[CrawlerTestCase]:
    test_cases: list[CrawlerTestCase] = []
    for domain, cases in sorted(data.items()):
        test_cases.extend(_TEST_CASE_ADAPTER.validate_python({"domain": domain} | case) for case in cases)
    return test_cases


def load() -> list[CrawlerTestCase]:
    return parse_cases(load_cases())
