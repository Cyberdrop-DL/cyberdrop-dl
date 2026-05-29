from __future__ import annotations

import base64
import contextlib
import copy
import datetime
import logging
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, Self, overload

import yarl

from cyberdrop_dl.utils.filepath import sanitize_folder

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from cyberdrop_dl import signature
    from cyberdrop_dl.manager import Manager

    class AbsoluteHttpURL(yarl.URL):
        @signature.copy(yarl.URL.__new__)
        def __new__(cls) -> Self: ...

        @signature.copy(yarl.URL.__truediv__)
        def __truediv__(self, name: str) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.__mod__)
        def __mod__(self, query: object) -> AbsoluteHttpURL: ...

        @property
        def host(self) -> str: ...  # pyright: ignore[reportIncompatibleVariableOverride]

        @property
        def scheme(self) -> Literal["http", "https"]: ...  # pyright: ignore[reportIncompatibleVariableOverride]

        @property
        def absolute(self) -> Literal[True]: ...  # pyright: ignore[reportIncompatibleVariableOverride]

        @property
        def parent(self) -> AbsoluteHttpURL: ...  # pyright: ignore[reportIncompatibleVariableOverride]

        @signature.copy(yarl.URL.with_path)
        def with_path(self) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.with_host)
        def with_host(self) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.origin)
        def origin(self) -> AbsoluteHttpURL: ...

        @overload
        def with_query(self, query: yarl.Query) -> AbsoluteHttpURL: ...

        @overload
        def with_query(self, **kwargs: yarl.QueryVariable) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.with_query)
        def with_query(self) -> AbsoluteHttpURL: ...

        @overload
        def extend_query(self, query: yarl.Query) -> AbsoluteHttpURL: ...

        @overload
        def extend_query(self, **kwargs: yarl.QueryVariable) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.extend_query)
        def extend_query(self) -> AbsoluteHttpURL: ...

        @overload
        def update_query(self, query: yarl.Query) -> AbsoluteHttpURL: ...

        @overload
        def update_query(self, **kwargs: yarl.QueryVariable) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.update_query)
        def update_query(self) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.without_query_params)
        def without_query_params(self) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.with_fragment)
        def with_fragment(self) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.with_name)
        def with_name(self) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.with_suffix)
        def with_suffix(self) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.join)
        def join(self) -> AbsoluteHttpURL: ...

        @signature.copy(yarl.URL.joinpath)
        def joinpath(self) -> AbsoluteHttpURL: ...

else:
    AbsoluteHttpURL = yarl.URL


class ScrapeItemType(IntEnum):
    FORUM = 0
    FORUM_POST = 1
    FILE_HOST_PROFILE = 2
    FILE_HOST_ALBUM = 3


FORUM = ScrapeItemType.FORUM
FORUM_POST = ScrapeItemType.FORUM_POST
FILE_HOST_PROFILE = ScrapeItemType.FILE_HOST_PROFILE
FILE_HOST_ALBUM = ScrapeItemType.FILE_HOST_ALBUM


logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class MediaItem:
    url: AbsoluteHttpURL
    domain: str
    referer: AbsoluteHttpURL
    download_folder: Path
    filename: str
    original_filename: str = ""
    download_filename: str | None = None
    filesize: int | None = None
    ext: str
    db_path: str

    debrid_link: AbsoluteHttpURL | None = None
    duration: float | None = None
    is_segment: bool = False
    album_id: str | None = None
    uploaded_at: int | None = None

    parents: list[AbsoluteHttpURL] = field(default_factory=list)
    parent_threads: set[AbsoluteHttpURL] = field(default_factory=set)

    attempts: int = 0
    partial_file: Path = None  # pyright: ignore[reportAssignmentType]
    path: Path = None  # pyright: ignore[reportAssignmentType]
    hash: str | None = None
    downloaded: bool = field(default=False)

    metadata: object = field(init=False, default_factory=dict)

    uploaded_at_date: datetime.datetime | None = field(init=False, default=None)
    extra_info: dict[str, Any] = field(init=False, default_factory=dict)

    id: tuple[str, ...] = field(init=False)
    base64_id: str = field(init=False)
    headers: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = self.domain, self.db_path
        self.original_filename = self.original_filename or self.filename
        if self.url.scheme == "metadata":
            self.db_path = ""
            self.id = *self.id, "metadata"

        if self.uploaded_at:
            assert isinstance(self.uploaded_at, int), f"Invalid {self.uploaded_at =!r} from {self.referer}"
            self.uploaded_at_date = datetime.datetime.fromtimestamp(self.uploaded_at, tz=datetime.UTC)

        self.base64_id = base64.urlsafe_b64encode("".join(self.id).encode()).decode().rstrip("=")

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def real_url(self) -> AbsoluteHttpURL:
        return self.debrid_link or self.url

    @property
    def unique_temp_path(self) -> Path:
        return self.path.parent / f"{self.base64_id}.part"

    @staticmethod
    def from_item(  # noqa: PLR0913
        origin: ScrapeItem | MediaItem,
        url: AbsoluteHttpURL,
        domain: str,
        /,
        *,
        download_folder: Path,
        filename: str,
        db_path: str,
        original_filename: str | None = None,
        ext: str = "",
    ) -> MediaItem:
        return MediaItem(
            url=url,
            domain=domain,
            download_folder=download_folder,
            filename=filename,
            db_path=db_path,
            referer=origin.url,
            album_id=origin.album_id,
            ext=ext or Path(filename).suffix,
            original_filename=original_filename or filename,
            parents=origin.parents.copy(),
            uploaded_at=origin.uploaded_at,
            parent_threads=origin.parent_threads.copy(),
        )

    def serialize(self) -> dict[str, Any]:
        me = asdict(self)
        if self.hash:
            me["hash"] = f"xxh128:{self.hash}"
        for name in ("is_segment",):
            del me[name]
        return me


@dataclass(kw_only=True, slots=True)
class ScrapeItem:
    url: AbsoluteHttpURL
    part_of_album: bool = False
    album_id: str | None = None
    uploaded_at: int | None = None
    retry_path: Path | None = None
    folders: list[str] = field(init=False, default_factory=list)
    download_folder: Path = Path("downloads")

    parents: list[AbsoluteHttpURL] = field(default_factory=list, init=False)
    parent_threads: set[AbsoluteHttpURL] = field(default_factory=set, init=False)
    children: int = field(default=0, init=False)
    children_limit: int = field(default=0, init=False)
    type: ScrapeItemType | None = field(default=None, init=False)
    completed_at: int | None = field(default=None, init=False)
    created_at: int | None = field(default=None, init=False)
    children_limits: list[int] = field(default_factory=list, init=False)
    password: str | None = field(default=None, init=False)

    @contextlib.contextmanager
    def track_changes(self) -> Generator[Self]:
        old_url = self.url
        try:
            yield self
        finally:
            if old_url != self.url:
                logger.info(f"URL transformation applied: \n  {old_url = !s}\n  new_url = {self.url}")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(url={self.url!r}, folders={self.folders!r}, uploaded_at={self.uploaded_at!r}"

    def __post_init__(self) -> None:
        self.password = self.url.query.get("password")

    def append_folders(self, *folders: str) -> None:
        for folder in folders:
            self._append_folder(folder)

    def _append_folder(self, folder: str, /) -> None:
        if not folder or self.retry_path:
            return

        folder = sanitize_folder(folder)
        if _has_domain(folder) and (last_domain := _extract_last_domain(self.folders)):
            folder = _remove_domain_if_duplicate(folder, last_domain)

        self.folders.append(folder)

    def _set_type(self, scrape_item_type: ScrapeItemType | None, _: Manager | None = None) -> None:
        self.type = scrape_item_type
        self.children = self.children_limit = 0
        if self.type is None:
            return
        try:
            self.children_limit = self.children_limits[self.type]
        except (IndexError, TypeError):
            pass

    def add_children(self, number: int = 1) -> None:
        self.children += number
        if self.children_limit and self.children >= self.children_limit:
            from cyberdrop_dl.exceptions import MaxChildrenError

            raise MaxChildrenError(origin=self)

    def reset(self, *, reset_parents: bool = False, reset_parent_title: bool = False) -> None:
        """Resets `album_id`, `type` and `posible_datetime` back to `None`

        Reset `part_of_album` back to `False`
        """
        self.album_id = self.uploaded_at = None
        self._set_type(None)
        self.part_of_album = False
        if reset_parents:
            self.parents = []
            self.parent_threads = set()
        if reset_parent_title:
            self.folders.clear()

    def setup_as(self, title: str, type_: ScrapeItemType, /, *, album_id: str | None = None) -> None:
        self.part_of_album = True
        if album_id:
            self.album_id = album_id
        if self.type != type_:
            self._set_type(type_)
        self.append_folders(title)

    def create_new(
        self,
        url: AbsoluteHttpURL,
        *,
        part_of_album: bool = False,
        album_id: str | None = None,
        add_parent: AbsoluteHttpURL | bool | None = None,
    ) -> Self:
        """Creates a scrape item."""
        from cyberdrop_dl.utils import is_absolute_http_url

        scrape_item = self.copy()
        assert is_absolute_http_url(url)

        if add_parent:
            new_parent = add_parent if isinstance(add_parent, AbsoluteHttpURL) else self.url
            assert is_absolute_http_url(new_parent)
            scrape_item.parents.append(new_parent)

        scrape_item.url = url
        scrape_item.part_of_album = part_of_album or scrape_item.part_of_album
        scrape_item.album_id = album_id or scrape_item.album_id
        return scrape_item

    def create_child(self, url: AbsoluteHttpURL) -> Self:
        return self.create_new(url, part_of_album=True, add_parent=True)

    def setup_as_album(self: ScrapeItem, title: str, *, album_id: str | None = None) -> None:
        return self.setup_as(title, FILE_HOST_ALBUM, album_id=album_id)

    def setup_as_profile(self: ScrapeItem, title: str, *, album_id: str | None = None) -> None:
        return self.setup_as(title, FILE_HOST_PROFILE, album_id=album_id)

    def setup_as_forum(self: ScrapeItem, title: str, *, album_id: str | None = None) -> None:
        return self.setup_as(title, FORUM, album_id=album_id)

    def setup_as_post(self: ScrapeItem, title: str, *, album_id: str | None = None) -> None:
        return self.setup_as(title, FORUM_POST, album_id=album_id)

    @property
    def origin(self) -> AbsoluteHttpURL | None:
        if self.parents:
            return self.parents[0]

    @property
    def parent(self) -> AbsoluteHttpURL | None:
        if self.parents:
            return self.parents[-1]

    @property
    def is_loose_file(self) -> bool:
        return not self.folders or not self.part_of_album

    @property
    def path(self) -> Path:
        if self.retry_path:
            return self.retry_path
        return Path(*self.folders)

    def compose_download_path(self, domain: str) -> Path:
        if self.retry_path:
            return self.retry_path
        path = self.download_folder / self.path
        if self.is_loose_file:
            path = path / f"Loose Files ({domain})"
        return path

    def copy(self) -> Self:
        """Returns a deep copy of this scrape_item"""
        return copy.deepcopy(self)


class QueryDatetimeRange(NamedTuple):
    before: datetime.datetime | None = None
    after: datetime.datetime | None = None

    @staticmethod
    def from_url(url: AbsoluteHttpURL) -> QueryDatetimeRange | None:
        self = QueryDatetimeRange(_date_from_query_param(url, "before"), _date_from_query_param(url, "after"))
        if self == (None, None):
            return None
        if (self.before and self.after) and (self.before <= self.after):
            raise ValueError
        return self

    def is_in_range(self, other: datetime.datetime) -> bool:
        return not ((self.before and other >= self.before) or (self.after and other <= self.after))

    def as_query(self) -> dict[str, Any]:
        return {name: value.isoformat() for name, value in self._asdict().items() if value}


def _date_from_query_param(url: AbsoluteHttpURL, query_param: str) -> datetime.datetime | None:
    from cyberdrop_dl.utils.dates import parse_iso

    if value := url.query.get(query_param):
        return parse_iso(value)


def _has_domain(folder: str) -> bool:
    return folder.endswith(")") and " (" in folder


def _remove_domain_if_duplicate(folder: str, last_domain: str) -> str:
    og_folder, _, current_domain = folder.rpartition(" (")
    if last_domain == current_domain[:-1]:
        return og_folder
    return folder


def _extract_last_domain(folders: Sequence[str]) -> str | None:
    for folder in reversed(folders):
        if folder.endswith(")"):
            try:
                return folder[folder.rindex("(") + 1 : -1]
            except IndexError:
                pass

    return None
