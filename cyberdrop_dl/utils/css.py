from __future__ import annotations

import dataclasses
import html
from typing import TYPE_CHECKING, cast, final, overload

from bs4 import BeautifulSoup, ResultSet
from bs4.filter import SoupStrainer

from cyberdrop_dl import aio
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import catch, strict_variadic, transform_generator

if TYPE_CHECKING:
    from collections.abc import Coroutine, Generator, Iterable, Iterator

    from bs4.element import Tag

    from cyberdrop_dl.constants import HttpMethod

__tracebackhide__ = True


def _choose_html_parser() -> str:
    try:
        __import__("lxml")
    except ImportError:
        return "html.parser"
    else:
        return "lxml"


HTML_PARSER = _choose_html_parser()

may_block = aio.may_block("select")


@may_block
def _soup_select(tag: Tag, selector: str) -> ResultSet[Tag]:
    return tag.select(selector)


@may_block
def _soup_select_one(tag: Tag, selector: str) -> Tag | None:
    return tag.select_one(selector)


@may_block
def _soup_iselect(tag: Tag, selector: str) -> Iterator[Tag]:
    return tag.css.iselect(selector)


class SelectorError(ScrapeError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(422, message)


@final
@dataclasses.dataclass(slots=True, frozen=True)
class Selector:
    css: str
    attribute: str = ""


@dataclasses.dataclass(slots=True)
class HTMLForm:
    method: HttpMethod
    action: str
    inputs: dict[str, str | None]


def _normalize_selector(selector: Selector | str, attribute: str | None = None) -> tuple[str, str | None]:
    if type(selector) is Selector:
        return selector.css, selector.attribute
    return selector, attribute


def _select_one(tag: Tag, selector: str) -> Tag:
    """Same as `tag.select_one` but asserts the result is not `None`"""
    result = _soup_select_one(tag, selector)
    if result is None:
        raise SelectorError(f"{selector} tag not found")
    return result


def select_text(tag: Tag, selector: Selector | str, *, strip: bool = True, decompose: str | None = None) -> str:
    """Same as `tag.select_one.get_text(strip=strip)` but asserts the result is not `None`"""
    selector, _ = _normalize_selector(selector, None)
    inner_tag = select(tag, selector)
    if decompose:
        _decompose(tag, decompose)
    return text(inner_tag, strip=strip)


def attr_or_none(tag: Tag, *attributes: str) -> str | None:
    """Same as `tag.get(attribute)` but asserts the result is a single str"""
    for attribute in attributes:
        if result := _attr_or_none(tag, attribute):
            return result


def _attr_or_none(tag: Tag, attribute: str) -> str | None:
    attribute_ = attribute
    if attribute_ == "srcset":
        if (srcset := tag.get(attribute_)) and type(srcset) is str:
            return best_from_srcset(srcset)
        attribute_ = "src"

    value = tag.get("data-src") or tag.get(attribute_) if attribute_ == "src" else tag.get(attribute_)
    if value is None:
        return None
    if type(value) is not str:
        raise SelectorError(f"Expected a single value for {attribute = !r}, got multiple")
    return value


def attr(tag: Tag, *attributes: str) -> str:
    """Same as `tag.get(attribute)` but asserts the result is not `None` and is a single string"""
    if result := attr_or_none(tag, *attributes):
        return result
    raise SelectorError(f"{attributes = } not found")


@may_block
def text(tag: Tag, *, strip: bool = True) -> str:
    return tag.get_text(strip=strip)


@overload
def select(tag: Tag, selector: str) -> Tag: ...


@overload
def select(tag: Tag, selector: str, attribute: str) -> str: ...


@overload
def select(tag: Tag, selector: Selector) -> str: ...


def select(tag: Tag, selector: Selector | str, attribute: str | None = None) -> Tag | str:
    selector, attribute = _normalize_selector(selector, attribute)
    inner_tag = _select_one(tag, selector)
    if not attribute:
        return inner_tag
    return attr(inner_tag, attribute)


@overload
def iselect(tag: Tag, selector: str) -> Iterable[Tag]: ...


@overload
def iselect(tag: Tag, selector: Selector) -> Iterable[str]: ...


@overload
def iselect(tag: Tag, selector: str, attribute: str) -> Iterable[str]: ...


def iselect(tag: Tag, selector: Selector | str, attribute: str | None = None) -> Iterable[Tag] | Iterable[str]:
    """Same as `tag.select(selector)`, but it returns a generator instead of a list."""
    selector, attribute = _normalize_selector(selector, attribute)
    tags = _soup_iselect(tag, selector)
    if not attribute:
        yield from tags

    else:
        for inner_tag in tags:
            if attr := attr_or_none(inner_tag, attribute):
                yield attr


def iselect_text(soup: Tag, /, selector: Selector | str, contains: tuple[str, ...] | str = ()) -> Iterable[str]:
    selector, _ = _normalize_selector(selector, None)
    contains = strict_variadic(contains)
    for tag in iselect(soup, selector):
        content = text(tag)
        if contains and not all(key in content for key in contains):
            continue
        yield content


def parse_srcset(srcset: str) -> Generator[tuple[str, str]]:
    for option in srcset.split(","):
        match option.strip().rsplit(maxsplit=1):
            case [url, decriptor]:
                yield decriptor, url
            case [url]:
                yield "1x", url
            case _:
                continue


def best_from_srcset(srcset: str) -> str:
    options = dict(parse_srcset(srcset))
    best = max(options, key=lambda decriptor: float(decriptor.rstrip("wx")))
    return options[best]


def _decompose(tag: Tag, selector: Selector | str) -> None:
    selector, _ = _normalize_selector(selector, None)
    for inner_tag in _soup_select(tag, selector):
        inner_tag.decompose()


def decompose(tag: Tag, *selectors: Selector | str) -> None:
    for trash in selectors:
        _decompose(tag, trash)


def rstrip_domain(title: str, domain: str) -> str:
    assert domain
    second_level_domain = domain.rsplit(".", 1)[0].casefold().removeprefix("www.")

    def sanitize(string: str, char: str) -> str:
        front, _, tail = string.rpartition(char)
        if front and second_level_domain in tail.casefold():
            return front.strip()
        return string

    for char in sorted(("|", " - "), key=title.rfind, reverse=True):
        title = sanitize(title, char)

    return title


def page_title(soup: Tag, domain: str | None = None) -> str:
    title = select_text(soup, "title")
    if domain:
        return rstrip_domain(title, domain)
    return title


def parse_form(form: Tag, /) -> HTMLForm:
    inputs: dict[str, str | None] = {}
    for elem in iselect(form, "input"):
        name = attr_or_none(elem, "name") or attr(elem, "id")
        inputs[name] = attr_or_none(elem, "value")

    method = attr(form, "method").upper()
    action = attr(form, "action")
    return HTMLForm(cast("HttpMethod", method), action, inputs)


def where(selector1: str, selector2: str, *selectors: str) -> str:
    selectors = selector1, selector2, *selectors
    return ":where(" + ", ".join(selectors) + ")"


@may_block
def soup(content: str, parse_only: tuple[str, ...] | str | None = None) -> BeautifulSoup:
    if not content:
        raise ScrapeError(204, "Received empty HTML response")
    return BeautifulSoup(content, HTML_PARSER, parse_only=SoupStrainer(parse_only) if parse_only is not None else None)


unescape = html.unescape

IFRAME = Selector("iframe", "src")
IMAGE = Selector("img", "srcset")
ANY_LINK = Selector(":any-link", "href")
VIDEO_SOURCE = Selector("video source", "src")

select_or_none = catch(select, SelectorError)
select_text_or_none = catch(select_text, SelectorError)
select_all = transform_generator(list)(iselect)


aselect = aio.to_thread(select)
aselect_text = aio.to_thread(select_text)
aiselect_text = aio.to_thread(transform_generator(list)(iselect_text))
asoup = aio.to_thread(soup)
apage_title = aio.to_thread(page_title)


@overload
def aiselect(tag: Tag, selector: str) -> aio.AsyncIteratorWrapper[Tag]: ...


@overload
def aiselect(tag: Tag, selector: Selector) -> Coroutine[None, None, list[str]]: ...


@overload
def aiselect(tag: Tag, selector: str, attribute: str) -> Coroutine[None, None, list[str]]: ...


def aiselect(
    tag: Tag, selector: Selector | str, attribute: str | None = None
) -> Coroutine[None, None, list[str]] | aio.AsyncIteratorWrapper[Tag]:
    selector, attribute = _normalize_selector(selector, attribute)
    if attribute:
        return _aselect_all_w_attributes(tag, selector, attribute)
    return _aiselect_tags(tag, selector)


@aio.to_thread
def _aselect_all_w_attributes(tag: Tag, selector: str, attribute: str) -> list[str]:
    return list(iselect(tag, selector, attribute))


@aio.iterable_to_thread
def _aiselect_tags(tag: Tag, selector: str) -> Iterable[Tag]:
    return iselect(tag, selector)
