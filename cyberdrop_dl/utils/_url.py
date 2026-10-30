from __future__ import annotations

from typing import TYPE_CHECKING, Generic, cast, overload

import yarl
from typing_extensions import TypeIs, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


def fix_query_params_encoding(link: str) -> str:
    if "?" not in link:
        return link
    parts, query_and_frag = link.split("?", 1)
    query_and_frag = query_and_frag.replace("+", "%20")
    return f"{parts}?{query_and_frag}"


def fix_multi_slashes(url: str) -> str:
    import re

    return re.sub(r"(^/|https?:/)/+", r"\1/", url, count=1)


def str_to_url(url: str) -> yarl.URL:
    if not url:
        raise ValueError("Empty URL", url)

    clean_url = fix_multi_slashes(fix_query_params_encoding(url))
    return yarl.URL(clean_url, encoded="%" in clean_url)


def parse_http_url(
    link: yarl.URL | str,
    relative_to: AbsoluteHttpURL | None = None,
    *,
    trim: bool = True,
) -> AbsoluteHttpURL:
    """Parse a string into an absolute URL, handling relative URLs, encoding and optionally removes trailing slash (trimming)."""

    url = str_to_url(link) if isinstance(link, str) else link
    if not _is_absolute_http_url(url):
        if not relative_to:
            raise ValueError("Relative URL with no known origin", url)
        url = resolve_url(url, relative_to)

    check_url(url)
    if not trim:
        return url
    return remove_trailing_slash(url)


def resolve_url(url: yarl.URL, origin: AbsoluteHttpURL) -> AbsoluteHttpURL:
    url = origin.join(url) if not url.absolute else url
    if not url.scheme:
        url = url.with_scheme(origin.scheme if origin else "https")
    if not _is_absolute_http_url(url):
        raise ValueError(f"Unable to parse an absolute URL from {url}")
    return url


def check_url(url: yarl.URL) -> None:
    if not url.host:
        raise ValueError("URL has no host", url)
    if "." not in url.host and url.host != "localhost":
        raise ValueError("URL has no TLD", url)


def remove_trailing_slash(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    if url.name or url.path == "/":
        return url
    return url.parent.with_fragment(url.fragment).with_query(url.query)


def matches_any_host(url: yarl.URL, hosts: Iterable[str]) -> bool:
    import yarl

    if not url.host:
        return False

    assert not isinstance(hosts, str)
    for host in hosts:
        if host in url.host:
            return True
        if host.startswith(("https://", "http://")) and yarl.URL(host).host == url.host:
            return True

    return False


def _is_absolute_http_url(url: yarl.URL) -> TypeIs[AbsoluteHttpURL]:
    return url.absolute and url.scheme in {"http", "https"}


def remove_query_params[T: yarl.URL](url: T, keep: tuple[str, ...]) -> T:
    return cast("T", url.with_query([(name, value) for name, value in url.query.items() if name in keep] or None))


def is_ip_address(address: str) -> bool:
    import ipaddress

    try:
        ipaddress.ip_address(address)
    except ValueError:
        return False
    else:
        return True


def is_url(obj: object) -> TypeIs[yarl.URL]:
    return type(obj) is yarl.URL


@overload
def sort_query(item: Mapping[str, str]) -> list[tuple[str, str]]: ...


@overload
def sort_query[T: yarl.URL](item: T) -> T: ...


def sort_query[T: yarl.URL](item: Mapping[str, str] | T) -> list[tuple[str, str]] | T:
    if is_url(item):
        return item.with_query(sort_query(item.query))

    return [(k, v) for k, v in item.items()]


def path_qs(url: yarl.URL) -> str:
    return url.path_qs


def path_qs_frag(url: yarl.URL) -> str:
    return f"{url.path_qs}#{url.fragment}" if url.fragment else url.path_qs


def path_frag(url: yarl.URL) -> str:
    return f"{url.path}#{url.fragment}" if url.fragment else url.path


def url_hash(url: yarl.URL) -> str:
    return str(sort_query(url))


def reverse_dns_name(host: str) -> tuple[str, ...]:
    return tuple(reversed(host.split(".")))


def is_within_domain(root_domain: str, host: str) -> bool:
    host = host.lower().removeprefix("www.")
    root_domain = root_domain.lower().removeprefix("www.")
    return (host == root_domain) or host.endswith("." + root_domain)


DedupeT = TypeVar("DedupeT", default=str)


# TODO: move to to base utils
class Deduper(Generic[DedupeT]):
    def __init__(self, get_key: Callable[[DedupeT], str] = str) -> None:
        self.seen: set[str] = set()
        self.get_key: Callable[[DedupeT], str] = get_key

    def __contains__(self, item: DedupeT) -> bool:
        lookup = self.get_key(item)
        if lookup in self.seen:
            return True
        self.seen.add(lookup)
        return False

    def __len__(self) -> int:
        return len(self.seen)

    def __iter__(self) -> Iterator[str]:
        return iter(self.seen)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(seen={self.seen!r})"

    def clear(self) -> None:
        return self.seen.clear()


class URLDeduper(Deduper[yarl.URL]):
    def __init__(self, url_id: Callable[[yarl.URL], str] = str) -> None:
        super().__init__(get_key=lambda url: url_id(sort_query(url)))
