from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, Literal, Self

from cyclopts import App, Parameter
from cyclopts.bind import normalize_tokens
from pydantic import (
    BaseModel,
    ByteSize,
    Field,
    PositiveInt,
    field_serializer,
    field_validator,
)

from cyberdrop_dl import yaml
from cyberdrop_dl.config.merge import merge_models
from cyberdrop_dl.models import AppriseURL  # noqa: TC001
from cyberdrop_dl.models.validators import falsy_as, to_bytesize
from cyberdrop_dl.utils.apprise import read_apprise_urls

from ._global import GlobalSettings
from .auth import AuthSettings
from .settings import ConfigSettings

if TYPE_CHECKING:
    from collections.abc import Iterable

    from yarl import URL

    from cyberdrop_dl.manager import AppData, Manager
    from cyberdrop_dl.models.types import ByteSizeSerilized, HttpURL, ListNonEmptyStr, NonEmptyStr


_app: App | None = None


MIN_REQUIRED_FREE_SPACE = to_bytesize("512MB")


@Parameter(name="*")
class Config(BaseModel):
    source: Annotated[Path | None, Parameter(show=False)] = None

    auth: AuthSettings = Field(default_factory=AuthSettings)
    settings: ConfigSettings = Field(default_factory=ConfigSettings)
    global_settings: GlobalSettings = Field(default_factory=GlobalSettings)

    deep_scrape: bool = False
    apprise_urls: Annotated[tuple[AppriseURL, ...], Parameter(show=False)] = ()

    ssl_context: Literal["truststore", "certifi", "truststore+certifi"] | None = "truststore+certifi"
    disable_crawlers: ListNonEmptyStr = []
    flaresolverr: HttpURL | None = None
    max_file_name_length: PositiveInt = 95
    max_folder_name_length: PositiveInt = 60
    proxy: HttpURL | None = None
    required_free_space: ByteSizeSerilized = to_bytesize("5GB")
    user_agent: NonEmptyStr = "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0"

    @field_validator("ssl_context", mode="before")
    @classmethod
    def ssl(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.lower().strip()
        return falsy_as(value, None)

    @field_validator("disable_crawlers", mode="after")
    @classmethod
    def unique_list(cls, value: list[str]) -> list[str]:
        return sorted(set(value))

    @field_serializer("flaresolverr", "proxy")
    def serialize(self, value: URL | str) -> URL | str | None:
        return falsy_as(value, None)

    @field_validator("flaresolverr", "proxy", mode="before")
    @classmethod
    def convert_to_str(cls, value: str) -> str | None:
        return falsy_as(value, None)

    @field_validator("required_free_space", mode="after")
    @classmethod
    def override_min(cls, value: ByteSize) -> ByteSize:
        return max(value, MIN_REQUIRED_FREE_SPACE)

    @classmethod
    def create(cls, appdata: AppData, config_file: Path | None = None) -> Self:

        global_settings = appdata.configs / "global_settings.yaml"
        auth_file = appdata.configs / "authentication.yaml"
        config_file = config_file or appdata.config_file
        apprise_file = config_file.parent / "apprise.txt"

        return cls(
            source=config_file,
            auth=_load_config_file(auth_file, AuthSettings),
            settings=_load_config_file(config_file, ConfigSettings),
            global_settings=_load_config_file(global_settings, GlobalSettings),
            apprise_urls=read_apprise_urls(apprise_file),
        )

    @classmethod
    def from_manager(cls, manager: Manager) -> Self:
        return cls.create(manager.appdata, manager.cli_args.config_file)

    def update(self, other: Self) -> Self:
        return merge_models(self, other)

    @classmethod
    def parse_args(cls, tokens: str | Iterable[str]) -> Config:
        global _app  # noqa: PLW0603
        if _app is None:
            _app = App(print_error=False, exit_on_error=False)
            _ = _app.command(name="coerce")(_coerce)
        fn, bound, *_ = _app.parse_args(["coerce", *normalize_tokens(tokens)])
        assert fn is _coerce
        return _coerce(*bound.args, **bound.kwargs)


def _load_config_file[BaseModelT: BaseModel](file: Path, model: type[BaseModelT]) -> BaseModelT:
    try:
        content = yaml.load(file)
    except FileNotFoundError:
        default = model()
        yaml.save(file, default)
        return default
    else:
        return model.model_validate(content)


def _coerce(*, config: Config | None = None) -> Config:
    if config is None:
        return Config()
    return config


__all__ = ["AuthSettings", "Config", "ConfigSettings", "GlobalSettings"]
