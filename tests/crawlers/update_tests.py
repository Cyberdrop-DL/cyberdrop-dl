from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired

from typing_extensions import TypedDict

if TYPE_CHECKING:
    from collections.abc import Sequence


class Result(TypedDict):
    # Simplified version of media_item
    url: str
    filename: NotRequired[str | type]
    debrid_link: NotRequired[str | None | type]
    original_filename: NotRequired[str | type]
    referer: NotRequired[str | type]
    album_id: NotRequired[str | None | type]
    uploaded_at: NotRequired[int | None | type]
    download_folder: NotRequired[str | type]


@dataclasses.dataclass(slots=True)
class CrawlerTestCase:
    domain: str
    url: str
    results: list[Result]
    description: str | None = None
    fail: bool | str | int = False
    skip: str | bool = False
    count: Sequence[int] | int | None = None
    options: list[str] | None = None
    log: str | None = None


TestTuple = tuple[str, list[Result], int, Any]


def _load_test_data() -> None:
    if _TEST_DATA:
        return
    for file in (Path(__file__).parent / "test_cases").iterdir():
        if not file.name.startswith("_") and file.suffix == ".py":
            _load_test_cases(file)


_TEST_DATA: dict[str, list[TestTuple]] = {}


def _load_test_cases(path: Path) -> None:
    module_spec = importlib.util.spec_from_file_location(path.stem, path)
    assert module_spec and module_spec.loader
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    if module.DOMAIN in _TEST_DATA:
        raise RuntimeError(f"Multiple tests files for {module.DOMAIN}")
    _TEST_DATA[module.DOMAIN] = list(module.TEST_CASES)


def _save_test_data() -> None:
    base = Path(__file__).parent / "test_cases2"
    base.mkdir(exist_ok=True)
    for domain, test_cases in _TEST_DATA.items():
        name = domain.replace(".", "_") + ".py"

        file = base / name
        content = f"DOMAIN = {domain!r}\nTEST_CASES={list(cases(test_cases))!r}"

        for type, name in {int: "int", str: "str"}.items():
            content = content.replace(repr(type), name)

        file.write_text(content)


def cases(test_cases: list[TestTuple]):
    for test_case in test_cases:
        url, results, *rest = test_case
        case: dict[str, Any] = {"url": url, "results": results}
        if rest:
            case["count"] = rest[0]
        yield case


if __name__ == "__main__":
    _load_test_data()
    _save_test_data()
    print("DONE")
