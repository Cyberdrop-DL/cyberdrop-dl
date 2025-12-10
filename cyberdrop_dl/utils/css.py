from __future__ import annotations

import functools
import json
from typing import TYPE_CHECKING, Any, NamedTuple, ParamSpec, TypeVar, overload

import bs4.css
from bs4 import BeautifulSoup

from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils.logger import log_debug

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from bs4.element import Tag

    _P = ParamSpec("_P")
    _R = TypeVar("_R")


class SelectorError(ScrapeError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(422, message)


class CssAttributeSelector(NamedTuple):
    element: str
    attribute: str = ""

    def __call__(self, soup: Tag) -> str:
        return select(soup, self.element, self.attribute)


def not_none(func: Callable[_P, _R | None]) -> Callable[_P, _R]:
    @functools.wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        result = func(*args, **kwargs)
        if result is None:
            raise SelectorError
        return result

    return wrapper


@not_none
def _select_one(tag: Tag, selector: str) -> Tag | None:
    """Same as `tag.select_one` but asserts the result is not `None`"""
    return tag.select_one(selector)


def select_text(tag: Tag, selector: str, strip: bool = True, *, decompose: str | None = None) -> str:
    """Same as `tag.select_one.get_text(strip=strip)` but asserts the result is not `None`"""
    inner_tag = select(tag, selector)
    if decompose:
        for trash in iselect(inner_tag, decompose):
            trash.decompose()
    return get_text(inner_tag, strip)


def get_attr_or_none(tag: Tag, attribute: str) -> str | None:
    """Same as `tag.get(attribute)` but asserts the result is a single str"""
    attribute_ = attribute
    if attribute_ == "srcset":
        if (srcset := tag.get(attribute_)) and isinstance(srcset, str):
            return _parse_srcset(srcset)
        attribute_ = "src"

    if attribute_ == "src":
        value = tag.get("data-src") or tag.get(attribute_)
    else:
        value = tag.get(attribute_)
    if isinstance(value, list):
        raise SelectorError(f"Expected a single value for {attribute = !r}, got multiple")
    return value


def get_text(tag: Tag, strip: bool = True) -> str:
    return tag.get_text(strip=strip)


@not_none
def get_attr(tag: Tag, attribute: str) -> str | None:
    """Same as `tag.get(attribute)` but asserts the result is not `None` and is a single string"""
    return get_attr_or_none(tag, attribute)


@overload
def select(tag: Tag, selector: str) -> Tag: ...


@overload
def select(tag: Tag, selector: str, attribute: str) -> str: ...


def select(tag: Tag, selector: str, attribute: str | None = None) -> Tag | str:
    inner_tag = _select_one(tag, selector)
    if not attribute:
        return inner_tag
    return get_attr(inner_tag, attribute)


def select_one_get_attr_or_none(tag: Tag, selector: str, attribute: str) -> str | None:
    if inner_tag := tag.select_one(selector):
        return get_attr_or_none(inner_tag, attribute)


def iselect(tag: Tag, selector: str) -> Generator[Tag]:
    """Same as `tag.select(selector)`, but it returns a generator instead of a list."""
    yield from bs4.css.CSS(tag).iselect(selector)


def _parse_srcset(srcset: str) -> str:
    # The best src is the last one (usually)
    return [src.split(" ")[0] for src in srcset.split(", ")][-1]


def iget(tag: Tag, selector: str, attribute: str) -> Generator[str]:
    for inner_tag in iselect(tag, selector):
        if link := get_attr_or_none(inner_tag, attribute):
            yield link


def decompose(tag: Tag, selector: str) -> None:
    for inner_tag in tag.select(selector):
        inner_tag.decompose()


def sanitize_page_title(title: str, domain: str) -> str:
    sld = domain.rsplit(".", 1)[0].casefold()

    def clean(string: str, char: str):
        if char in string:
            front, _, tail = string.rpartition(char)
            if sld in tail.casefold():
                string = front.strip()
        return string

    return clean(clean(title, "|"), " - ")


def page_title(soup: Tag, domain: str | None = None) -> str:
    title = select_text(soup, "title")
    if domain:
        return sanitize_page_title(title, domain)
    return title


def get_json_ld_date(soup: Tag) -> str:
    return get_json_ld(soup)["uploadDate"]


def get_json_ld(soup: Tag, /, contains: str | None = None) -> dict[str, Any]:
    selector = "script[type='application/ld+json']"
    if contains:
        selector += f":-soup-contains('{contains}')"

    ld_json = json.loads(select_text(soup, selector)) or {}
    if isinstance(ld_json, list):
        return ld_json[0]

    return ld_json


def get_nuxt_data(soup: Tag) -> list[Any]:
    return json.loads(select_text(soup, "script#__NUXT_DATA__"))


def parse_nuxt_obj(nuxt_data: list[Any], *attributes: str) -> dict[str, Any]:
    """Parses a single object from a NUXT rich JSON payload response (__NUXT_DATA__)

    It iterates over each object until it finds an object with the desired attributes"""
    if obj := next(parse_nuxt_objs(nuxt_data, *attributes), None):
        return obj
    raise SelectorError(f"Unable to find object with {attributes = } in NUXT_DATA")


def parse_nuxt_objs(nuxt_data: list[Any], *attributes: str) -> Generator[dict[str, Any]]:
    """
    Iterates over each object from a NUXT rich JSON payload response (__NUXT_DATA__)

    It bypasses the devalue parsing logic by ignoring objects without the desired attributes

    https://github.com/nuxt/nuxt/discussions/20879
    """
    assert attributes
    first_key = attributes[0]
    objects = (obj for obj in nuxt_data if isinstance(obj, dict) and all(key in obj for key in attributes))
    for obj in objects:
        try:
            index: int = obj[first_key]
            index_map: dict[str, int] = nuxt_data[index]
        except LookupError:
            index_map = obj

        yield _parse_nuxt_obj(nuxt_data, index_map)


def _parse_nuxt_obj(nuxt_data: list[Any], index_map: dict[str, int]) -> dict[str, Any]:
    def hydrate(value: Any) -> Any:
        if isinstance(value, list):
            match value:
                case ["BigInt", val]:
                    return int(val)
                case ["Date" | "Object" | "RegExp", val, *_]:
                    return val
                case ["Set", *values]:
                    return [hydrate(nuxt_data[idx]) for idx in values]
                case ["Map", *values]:
                    return hydrate(dict(zip(*(iter(values),) * 2, strict=True)))
                case ["ShallowRef" | "ShallowReactive" | "Ref" | "Reactive" | "NuxtError", idx]:
                    return hydrate(nuxt_data[idx])
                case [str(name), *rest]:
                    log_debug(f"Unable to parse custom object {name} {rest}", 30)
                    return None
                case _:
                    return [hydrate(nuxt_data[idx]) for idx in value]

        if isinstance(value, dict):
            return _parse_nuxt_obj(nuxt_data, value)

        return value

    return {name: hydrate(nuxt_data[idx]) for name, idx in index_map.items()}


def unescape(html: str) -> str:
    return make_soup(html).get_text()


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


iframes = CssAttributeSelector("iframe", "src")
images = CssAttributeSelector("img", "srcset")
links = CssAttributeSelector(":any-link", "href")
