from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, final

from cyclopts import App, Parameter
from cyclopts.bind import normalize_tokens
from pydantic import AfterValidator, BaseModel, Field, NonNegativeInt, PositiveInt

from cyberdrop_dl import yaml
from cyberdrop_dl.config.appdata import AppData
from cyberdrop_dl.constants import DEFAULT_DOWNLOAD_PATH
from cyberdrop_dl.exceptions import CDLConfigRuntimeErrorsGroup
from cyberdrop_dl.models import ConfigModel
from cyberdrop_dl.models.types import ByteSizeSerilized, FalsyAsTuple  # noqa: TC001
from cyberdrop_dl.models.validators import to_bytesize
from cyberdrop_dl.utils import cleanup

from .auth import Authentication, Notifications
from .crawlers import Crawlers
from .filters import Filters
from .settings import Downloads, Hashing, Jdownloader, Logs, Network, Sort, SubFolders, UIOptions

if TYPE_CHECKING:
    from collections.abc import Iterable


MIN_REQUIRED_FREE_SPACE = to_bytesize("512MB")
MODULE_PATH = Path(__file__).parent
logger = logging.getLogger(__name__)
_app: App | None = None


@final
class Files:
    DEFAULT: Path = MODULE_PATH / "default.json"
    SCHEMA: Path = MODULE_PATH / "schema.json"

    @staticmethod
    def update() -> None:
        import json

        Files.SCHEMA.write_text(json.dumps(Config.model_json_schema(), indent=2, ensure_ascii=False))
        Files.DEFAULT.write_text(Config().model_dump_json(indent=2))


@Parameter(name="*")
class Config(ConfigModel, title="cyberdrop-dl config"):
    __final__: Literal[True] = True

    auth: Authentication = Field(default_factory=Authentication)
    cookies: Path | None = None
    "File/folder to import cookies from (.txt Netscape files)"

    crawlers: Crawlers = Field(default_factory=Crawlers)
    deep_scrape: bool = False
    "Make additional requests while scraping (slower)"

    delete_empty_folders: bool = True
    "Delete empty files and folders after a run"

    delete_partial_files: bool = False
    "Delete partial files after a run"

    download_folder: Annotated[Path, Parameter(alias=("--output", "-o", "-d"))] = DEFAULT_DOWNLOAD_PATH
    "Base output path for all downloads"

    downloads: Downloads = Field(default_factory=Downloads)
    dump_json: Annotated[bool, Parameter(alias="-j")] = False
    "Save details about each file (both skipped and downloaded) to a .jsonl file"

    filters: Filters = Field(default_factory=Filters)
    hashing: Hashing = Field(default_factory=Hashing)
    ignore_history: bool = False
    "Download files even if the alrady are maked as downloaded on the database"

    jdownloader: Jdownloader = Field(default_factory=Jdownloader)
    logs: Logs = Field(default_factory=Logs)
    max_children: FalsyAsTuple[NonNegativeInt] = ()
    "Limit the number of items to scrape per category"

    max_file_name_length: PositiveInt = 95
    "Max number of characters a filename should have. Filenames longer that this will be truncated"

    max_folder_name_length: PositiveInt = 60
    "Max number of characters a folder should have. Filenames longer that this will be truncated"

    max_thread_depth: NonNegativeInt = 0
    "Restricts how many levels of nested threads are scraped on a forum"

    max_thread_folder_depth: NonNegativeInt | None = None
    "Max number of nested folders CDL will create when maximum_thread_depth is greater that 0"

    min_free_space: Annotated[ByteSizeSerilized, AfterValidator(lambda x: max(x, MIN_REQUIRED_FREE_SPACE))] = (
        to_bytesize("5GB")
    )
    "Mininum free space require to start new downloads"

    mtime: bool = True
    "Use original upload date as modification date for downloded file"

    network: Network = Field(default_factory=Network)
    notifications: Notifications = Field(default_factory=Notifications)
    show_stats: Annotated[bool, Parameter(name="stats")] = True
    "Show stats report at the end of a run"

    sort: Sort = Field(default_factory=Sort)
    subfolders: SubFolders = Field(default_factory=SubFolders)
    ui: UIOptions = Field(default_factory=UIOptions)

    _resolved: bool = False
    _source: Path | None = None

    def __repr_args__(self) -> list[tuple[str, Path | None]]:
        return [("source", self._source)]

    @property
    def source(self) -> Path | None:
        return self._source

    def save_to(self, file: Path) -> None:
        yaml.save(file, self.model_dump(mode="json"))

    @staticmethod
    def from_file(file: Path, *, _save_if_not_found: bool = False) -> Config:
        try:
            content = yaml.load(file)
        except FileNotFoundError:
            default = Config()
            if _save_if_not_found:
                default.save_to(file)
            return default

        config = Config.model_validate(content)
        config._source = file
        return config

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

        default_log_folder = AppData.default().logs_folder
        self.logs.resolve_filenames(default_log_folder)
        _resolve_paths(self)
        if self.logs.expire_after:
            self.logs.delete_old_logs_and_folders()
            cleanup.rm_empty_dirs(self.logs.effective_log_folder)
        self._resolved = True


def _resolve_paths(model: BaseModel) -> None:
    for field_name, field_value in model:
        if isinstance(field_value, Path):
            if "{config}" in str(field_value):
                error = ValueError(
                    f"Using '{{config}}' as reference on a path is no longer supported: {field_value} ({field_name})"
                )
                raise CDLConfigRuntimeErrorsGroup("Invalid config", (error,))

            object.__setattr__(model, field_name, field_value.expanduser().resolve().absolute())

        elif isinstance(field_value, BaseModel):
            _resolve_paths(field_value)


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


__all__ = ["Config", "Files"]
