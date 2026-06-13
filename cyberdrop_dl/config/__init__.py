import importlib.util
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Literal, Self

from cyclopts import App, Parameter
from cyclopts.bind import normalize_tokens
from pydantic import BaseModel, ByteSize, Field, PositiveInt, field_serializer, field_validator
from yarl import URL

from cyberdrop_dl import yaml
from cyberdrop_dl.config.merge import merge_models
from cyberdrop_dl.manager import AppData, Manager
from cyberdrop_dl.models import AppriseURL
from cyberdrop_dl.models.types import ByteSizeSerilized, HttpURL, ListNonEmptyStr, NonEmptyStr
from cyberdrop_dl.models.validators import falsy_as, to_bytesize

from .auth import AuthSettings
from .settings import (
    Cookies,
    DownloadOptions,
    DupeCleanup,
    Files,
    FileSizeLimits,
    GenericCrawlerInstances,
    IgnoreOptions,
    Logs,
    MediaDurationLimits,
    RateLimiting,
    RuntimeOptions,
    Sorting,
    UIOptions,
)

_app: App | None = None
MIN_REQUIRED_FREE_SPACE = to_bytesize("512MB")
logger = logging.getLogger(__name__)


@Parameter(name="*")
class Config(BaseModel):
    source: Annotated[Path | None, Parameter(show=False)] = None

    auth: Annotated[AuthSettings, Parameter(show=False)] = Field(default_factory=AuthSettings)

    deep_scrape: bool = False
    apprise_urls: tuple[AppriseURL, ...] = ()

    ssl_context: Literal["truststore", "certifi", "truststore+certifi"] | None = "truststore+certifi"
    disable_crawlers: ListNonEmptyStr = []
    flaresolverr: HttpURL | None = None
    max_file_name_length: PositiveInt = 95
    max_folder_name_length: PositiveInt = 60
    proxy: HttpURL | None = None
    required_free_space: ByteSizeSerilized = to_bytesize("5GB")
    user_agent: NonEmptyStr = "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0"

    rate_limiting_options: RateLimiting = Field(default_factory=RateLimiting)
    ui_options: UIOptions = Field(default_factory=UIOptions)
    generic_crawlers_instances: GenericCrawlerInstances = Field(default_factory=GenericCrawlerInstances)

    cookies: Cookies = Field(default_factory=Cookies)
    download_options: DownloadOptions = Field(default_factory=DownloadOptions)
    dupe_cleanup_options: DupeCleanup = Field(default_factory=DupeCleanup)
    file_size_limits: FileSizeLimits = Field(default_factory=FileSizeLimits)
    media_duration_limits: MediaDurationLimits = Field(default_factory=MediaDurationLimits)
    files: Files = Field(default_factory=Files)
    ignore_options: IgnoreOptions = Field(default_factory=IgnoreOptions)
    logs: Logs = Field(default_factory=Logs)
    runtime_options: RuntimeOptions = Field(default_factory=RuntimeOptions)
    sorting: Sorting = Field(default_factory=Sorting)
    _resolved: bool = False

    @classmethod
    def create(cls, appdata: AppData, config_file: Path | None = None) -> Self:
        config_file = config_file or appdata.config_file

        self = _load_config_file(config_file, cls)
        if self.apprise_urls and importlib.util.find_spec("apprise") is None:
            logger.warning("Found apprise URLs for notifications but apprise is not installed. Ignoring")
            self.apprise_urls = ()
        return self

    @classmethod
    def from_manager(cls, manager: Manager) -> Self:
        return cls.create(manager.appdata, manager.cli_args.config_file)

    def update(self, other: Self) -> Self:
        return merge_models(self, other)

    @classmethod
    def parse_args(cls, tokens: str | Iterable[str]) -> "Config":
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
        self._resolve_paths(self)
        self.logs.delete_old_logs_and_folders()
        self._resolved = True

    @classmethod
    def _resolve_paths(cls, model: BaseModel) -> None:

        for name, value in vars(model).items():
            if isinstance(value, Path):
                if "{config}" in str(value):
                    raise RuntimeError(
                        f"Using '{{config}}' as reference on a path is no longer supported: {value} ({name})"
                    )

                object.__setattr__(model, name, value.expanduser().resolve().absolute())

            elif isinstance(value, BaseModel):
                cls._resolve_paths(value)

    @field_validator("ssl_context", mode="before")
    @classmethod
    def _ssl(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.lower().strip()
        return falsy_as(value, None)

    @field_validator("disable_crawlers", mode="after")
    @classmethod
    def _unique_list(cls, value: list[str]) -> list[str]:
        return sorted(set(value))

    @field_serializer("flaresolverr", "proxy")
    def _serialize(self, value: URL | str) -> URL | str | None:
        return falsy_as(value, None)

    @field_validator("flaresolverr", "proxy", mode="before")
    @classmethod
    def _to_str(cls, value: str) -> str | None:
        return falsy_as(value, None)

    @field_validator("required_free_space", mode="after")
    @classmethod
    def _override_min_storage(cls, value: ByteSize) -> ByteSize:
        return max(value, MIN_REQUIRED_FREE_SPACE)


def _load_config_file[BaseModelT: BaseModel](file: Path, model: type[BaseModelT]) -> BaseModelT:
    try:
        content = yaml.load(file)
    except FileNotFoundError:
        default = model()
        yaml.save(file, default)
        return default
    else:
        return model.model_validate(content, extra="forbid")


def _coerce(*, config: Config | None = None) -> Config:
    if config is None:
        return Config()
    return config


__all__ = ["AuthSettings", "Config"]
