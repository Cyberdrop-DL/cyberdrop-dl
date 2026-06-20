from pathlib import Path
from typing import Annotated

from cyclopts import Parameter
from cyclopts.core import App

from cyberdrop_dl import __version__
from cyberdrop_dl.models import ConfigModel
from cyberdrop_dl.models.types import HttpURL


@Parameter(name="*")
class CLIargs(ConfigModel):
    links: Annotated[tuple[HttpURL, ...], Parameter(show=False)] = ()
    "Link(s) to content to download (passing multiple links is supported"

    config_file: Path | None = None
    "YAML file to use as config"

    cache_file: Path | None = None
    "JSON file to use as cache"

    database_file: Path | None = None
    "SQLite file to use as database"

    download: bool = False
    "Skips UI, start download immediately"


app = App(
    name="cyberdrop-dl",
    help="Bulk asynchronous downloader for multiple file hosts",
    version=__version__,
    default_parameter=Parameter(negative_iterable=[], json_dict=False, json_list=False),
    result_action="return_value",
)


def register_commands() -> None:
    from cyberdrop_dl.cli.clean_up import app as cleanup
    from cyberdrop_dl.cli.database import app as database
    from cyberdrop_dl.cli.download import download
    from cyberdrop_dl.cli.hash import compute_hashes
    from cyberdrop_dl.cli.report import report
    from cyberdrop_dl.cli.show import show

    app.default(download)
    app.command(database)
    app.command(show)
    app.command(cleanup)
    app.command(report)
    app.command(compute_hashes, name="hash")


register_commands()
