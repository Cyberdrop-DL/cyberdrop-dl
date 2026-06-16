from pathlib import Path
from typing import Annotated, Literal

from cyclopts import Parameter
from cyclopts.core import App
from pydantic import BaseModel, Field

from cyberdrop_dl import __version__
from cyberdrop_dl.models.types import HttpURL


@Parameter(name="*")
class CLIargs(BaseModel):
    links: Annotated[tuple[HttpURL, ...], Parameter(show=False)] = Field(
        default=(),
        description="link(s) to content to download (passing multiple links is supported)",
    )
    appdata_folder: Path | None = Field(
        default=None,
        description="AppData folder path",
    )

    config_file: Path | None = Field(
        default=None,
        description="path to the CDL settings.yaml file to load",
    )

    download: bool = Field(
        default=False,
        description="skips UI, start download immediately",
    )
    impersonate: (
        Literal[
            "chrome",
            "edge",
            "safari",
            "safari_ios",
            "chrome_android",
            "firefox",
        ]
        | None
    ) = Field(
        default=None,
        description="Use this target as impersonation for all scrape requests",
    )


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
    from cyberdrop_dl.cli.show import show

    app.command(database)
    app.command(show)
    app.default(download)
    app.command(cleanup)


register_commands()
