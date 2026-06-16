from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, Self

from cyclopts import App, Parameter
from cyclopts.bind import normalize_tokens
from pydantic import BaseModel, ByteSize, Field, NonNegativeInt, PositiveInt, field_validator

from cyberdrop_dl import yaml
from cyberdrop_dl.constants import DEFAULT_DOWNLOAD_STORAGE
from cyberdrop_dl.exceptions import CDLConfigRuntimeErrorsGroup
from cyberdrop_dl.models import merge_models
from cyberdrop_dl.models.types import ByteSizeSerilized, ListNonNegativeInt  # noqa: TC001
from cyberdrop_dl.models.validators import to_bytesize
from cyberdrop_dl.utils import cleanup

from .auth import AuthSettings, Notifications
from .crawlers import Crawlers
from .settings import (
    Downloads,
    Filters,
    GenericCrawlers,
    Hashing,
    Jdownloader,
    Logs,
    MediaDurationLimits,
    Network,
    Sort,
    SubFolders,
    UIOptions,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


_app: App | None = None
MIN_REQUIRED_FREE_SPACE = to_bytesize("512MB")
logger = logging.getLogger(__name__)


@Parameter(name="*")
class Config(BaseModel):
    __final__: Literal[True] = True

    auth: AuthSettings = Field(default_factory=AuthSettings)
    cookies: Path | None = None
    "File/folder to import cookies from (.txt Netscape files)"

    crawlers: Crawlers = Field(default_factory=Crawlers)
    deep_scrape: bool = False
    delete_empty_folders: bool = True
    delete_partial_files: bool = False
    download_folder: Annotated[Path, Parameter(alias=("--output", "-o", "-d"))] = DEFAULT_DOWNLOAD_STORAGE
    downloads: Downloads = Field(default_factory=Downloads)
    dump_json: Annotated[bool, Parameter(alias="-j")] = False
    filters: Filters = Field(default_factory=Filters)
    generic_crawlers: GenericCrawlers = Field(default_factory=GenericCrawlers)
    hashing: Hashing = Field(default_factory=Hashing)
    ignore_history: bool = False
    jdownloader: Jdownloader = Field(default_factory=Jdownloader)
    logs: Logs = Field(default_factory=Logs)
    max_children: ListNonNegativeInt = []
    max_file_name_length: PositiveInt = 95
    max_folder_name_length: PositiveInt = 60
    max_thread_depth: NonNegativeInt = 0
    max_thread_folder_depth: NonNegativeInt | None = None
    media_duration_limits: MediaDurationLimits = Field(default_factory=MediaDurationLimits)
    min_free_space: ByteSizeSerilized = to_bytesize("5GB")
    mtime: bool = True
    network: Network = Field(default_factory=Network)
    notifications: Notifications = Field(default_factory=Notifications)
    show_stats: Annotated[bool, Parameter(name="stats")] = True
    "show stats report at the end of a run"

    sort: Sort = Field(default_factory=Sort)
    subfolders: SubFolders = Field(default_factory=SubFolders)
    ui: UIOptions = Field(default_factory=UIOptions)

    _resolved: bool = False
    _source: Path | None = None

    @property
    def source(self) -> Path | None:
        return self._source

    @staticmethod
    def from_file(file: Path, *, _save_if_not_found: bool = False) -> Config:
        try:
            content = yaml.load(file)
        except FileNotFoundError:
            default = Config()
            if _save_if_not_found:
                yaml.save(file, default.model_dump())
            return default

        config = Config.model_validate(content, extra="forbid")
        config._source = file
        return config

    def __or__(self, other: Self) -> Self:
        return merge_models(self, other)

    @staticmethod
    def parse_args(tokens: str | Iterable[str]) -> Config:
        global _app  # noqa: PLW0603
        if _app is None:
            _app = App(print_error=False, exit_on_error=False)
            _ = _app.command(name="coerce")(_coerce)
        fn, bound, *_ = _app.parse_args(["coerce", *normalize_tokens(tokens)])
        assert fn is _coerce
        return _coerce(*bound.args, **bound.kwargs)

    def resolve_paths(self) -> None:
        if self._resolved:
            return

        self.logs.resolve_filenames()
        _resolve_paths(self)
        if self.logs.expire_after:
            self.logs.delete_old_logs_and_folders()
            cleanup.rm_empty_dirs(self.logs.folder)
        self._resolved = True

    @field_validator("min_free_space", mode="after")
    @classmethod
    def _override_min_storage(cls, value: ByteSize) -> ByteSize:
        return max(value, MIN_REQUIRED_FREE_SPACE)


def _resolve_paths(model: BaseModel) -> None:
    for name, value in vars(model).items():
        if isinstance(value, Path):
            if "{config}" in str(value):
                error = ValueError(
                    f"Using '{{config}}' as reference on a path is no longer supported: {value} ({name})"
                )
                raise CDLConfigRuntimeErrorsGroup("Invalid config", (error,))

            object.__setattr__(model, name, value.expanduser().resolve().absolute())

        elif isinstance(value, BaseModel):
            _resolve_paths(value)


def merge_additive_args[T: list[str] | tuple[str, ...]](cli_values: T, config_values: Iterable[str]) -> T:
    match cli_values:
        case ["+", *_]:
            new_values = set(config_values).union(cli_values)
        case ["-", *_]:
            new_values = set(config_values) - set(cli_values)
        case _:
            return cli_values

    return type(cli_values)(sorted(new_values - {"+", "-"}))


def _coerce(*, config: Config | None = None) -> Config:
    if config is None:
        return Config()
    return config


__all__ = ["Config"]
