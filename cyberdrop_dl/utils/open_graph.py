"""The Open Graph protocol: https://ogp.me/"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from cyberdrop_dl.exceptions import ScrapeError

if TYPE_CHECKING:
    from collections.abc import Callable

    import bs4

_REQUIRED_ATTRS: Final = ("title", "type", "image", "url", "description")


def _make_selector(name: str) -> str:
    return f'meta[property^="og:{name}"][content], meta[name^="og:{name}"][content]'


_ALL = _make_selector("")


class OpenGraphError(ScrapeError):
    def __init__(self, property: str | int) -> None:
        super().__init__(422, f"Page have no {property} [og properties]")


class OpenGraph(dict[str, str | None]):
    """Open Graph properties"""

    title: str
    type: str
    image: str
    url: str
    description: str

    def __getattr__(self, name: str) -> str | None:
        value = self.get(name)
        if name in _REQUIRED_ATTRS and not value:
            raise OpenGraphError(name)
        return value

    def is_valid(self) -> bool:
        return all(self.get(attr) for attr in _REQUIRED_ATTRS)


def parse(soup: bs4.BeautifulSoup) -> OpenGraph:
    """Extracts Open Graph (og) properties from soup."""
    og_props = OpenGraph()
    for meta in soup.select(_ALL):
        if value := _get_attr(meta, "content"):
            try:
                name = _get_attr(meta, "property")
            except LookupError:
                name = _get_attr(meta, "name")

            name = name.removeprefix("og:").replace(":", "_")
            og_props[name] = value

    if not og_props.get("title") and (title := soup.select_one("title, h1")):
        og_props["title"] = title.get_text(strip=True)

    return og_props


def get(name: str, /, soup: bs4.BeautifulSoup) -> str | None:
    if meta := soup.select_one(_make_selector(name)):
        return _get_attr(meta, "content")


def _get_attr(meta: bs4.Tag, name: str) -> str:
    value = meta[name]
    assert isinstance(value, str)
    return value.strip()


def _make_parsers(name: str) -> tuple[Callable[[bs4.BeautifulSoup], str], Callable[[bs4.BeautifulSoup], str | None]]:
    def get_value(soup: bs4.BeautifulSoup) -> str | None:
        return get(name, soup)

    def _value(soup: bs4.BeautifulSoup) -> str:
        value = get_value(soup)
        if not value:
            raise OpenGraphError(name)
        return value

    return _value, get_value


video, get_video = _make_parsers("video")
image, get_image = _make_parsers("image")
title, get_title = _make_parsers("title")
description, get_description = _make_parsers("description")
