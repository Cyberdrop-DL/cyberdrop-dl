from pathlib import Path
from typing import Annotated, Literal

from cyclopts import Parameter
from cyclopts.core import App
from pydantic import BaseModel, Field, computed_field, field_validator

from cyberdrop_dl import __version__
from cyberdrop_dl.models.types import HttpURL
from cyberdrop_dl.progress import UIOptions


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
    download_tiktok_audios: bool = Field(
        default=False,
        description="download TikTok audios from posts and save them as separate files",
    )
    download_tiktok_src_quality_videos: bool = Field(
        default=False,
        description="download TikTok videos in source quality",
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

    portrait: bool = Field(
        default=False,
        description="force CDL to run with a vertical layout",
    )
    print_stats: bool = Field(
        default=True,
        description="show stats report at the end of a run",
    )
    ui: UIOptions = Field(
        default=UIOptions.FULLSCREEN,
        description="DISABLED, ACTIVITY, SIMPLE or FULLSCREEN",
    )

    @property
    def fullscreen_ui(self) -> bool:
        return self.ui == UIOptions.FULLSCREEN

    @computed_field
    def __computed__(self) -> dict[str, bool]:
        return {"fullscreen_ui": self.fullscreen_ui}

    @field_validator("ui", mode="before")
    @classmethod
    def lower(cls, value: str) -> str:
        return value.lower()


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
