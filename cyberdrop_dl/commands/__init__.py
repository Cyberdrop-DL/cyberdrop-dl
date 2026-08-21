import dataclasses
import logging
from collections.abc import Generator, Sequence
from pathlib import Path
from typing import Annotated, Any

from cyclopts import Parameter, Token, validators

logger = logging.getLogger(__name__)


def _resolve_path(type_: type[Path], tokens: Sequence[Token]) -> Path:
    assert len(tokens) == 1
    return type_(tokens[0].value).resolve()


def file_validator(ext: str | tuple[str, ...], *, exists: bool = True) -> Parameter:
    return Parameter(validator=validators.Path(exists=exists, dir_okay=False, ext=ext), converter=_resolve_path)


type YAMLFile = Annotated[Path, file_validator((".yaml", ".yml"))]
type JSONFile = Annotated[Path, file_validator(".json")]
type SQLiteFile = Annotated[Path, file_validator(".db")]


@Parameter(name="*")
@dataclasses.dataclass(slots=True)
class CLIarguments:
    config_file: Annotated[YAMLFile | None, Parameter(alias=("-c", "config"))] = None
    "YAML file to use as config"

    cache_file: JSONFile | None = None
    "JSON file to use as cache"

    database_file: Annotated[SQLiteFile | None, Parameter(alias=("db"))] = None
    "SQLite file to use as database"

    def __iter__(self) -> Generator[tuple[str, Path | None]]:
        for field in dataclasses.fields(self):
            yield field.name, getattr(self, field.name)

    def __json__(self) -> dict[str, Any]:
        return {k: None if v is None else str(v) for k, v in self}


def open_folder(folder: Path) -> None:
    if not folder.exists():
        from cyberdrop_dl.prompts import ask_should_create_folder

        if not ask_should_create_folder(folder):
            return

        folder.mkdir(parents=True)

    from cyberdrop_dl.utils import file_browser

    file_browser.open_folder(folder)
