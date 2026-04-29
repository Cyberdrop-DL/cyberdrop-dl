import datetime
from collections.abc import Iterable
from enum import auto
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from cyclopts import Parameter
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from cyberdrop_dl.compat import CIStrEnum
from cyberdrop_dl.models.types import HttpURL


class UIOptions(CIStrEnum):
    DISABLED = auto()
    ACTIVITY = auto()
    SIMPLE = auto()
    FULLSCREEN = auto()

    @property
    def is_disabled(self) -> bool:
        return self is UIOptions.DISABLED


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
    completed_after: datetime.date | None = Field(
        default=None,
        description="only retry downloads that were completed on or after this date",
    )
    completed_before: datetime.date | None = Field(
        default=None,
        description="only retry downloads that were completed on or before this date",
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
        | bool
        | None
    ) = Field(
        default=None,
        description="Use this target as impersonation for all scrape requests",
    )
    max_items_retry: int = Field(
        default=0,
        description="max number of links to retry",
    )
    portrait: bool = Field(
        default=False,
        description="force CDL to run with a vertical layout",
    )
    print_stats: bool = Field(
        default=True,
        description="show stats report at the end of a run",
    )
    retry_all: bool = Field(
        default=False,
        description="retry all downloads",
    )
    retry_failed: bool = Field(
        default=False,
        description="retry failed downloads",
    )
    retry_maintenance: bool = Field(
        default=False,
        description="retry download of maintenance files (bunkr). Requires files to be hashed",
    )
    ui: UIOptions = Field(
        default=UIOptions.FULLSCREEN,
        description="DISABLED, ACTIVITY, SIMPLE or FULLSCREEN",
    )

    @property
    def retry_any(self) -> bool:
        return any((self.retry_all, self.retry_failed, self.retry_maintenance))

    @property
    def fullscreen_ui(self) -> bool:
        return self.ui == UIOptions.FULLSCREEN

    @computed_field
    def __computed__(self) -> dict[str, bool]:
        return {"retry_any": self.retry_any, "fullscreen_ui": self.fullscreen_ui}

    @model_validator(mode="after")
    def mutually_exclusive(self) -> Self:
        group1 = [self.links, self.retry_all, self.retry_failed, self.retry_maintenance]
        msg1 = "`--links`, '--retry-all', '--retry-maintenace' and '--retry-failed' are mutually exclusive"
        _check_mutually_exclusive(group1, msg1)
        return self

    @field_validator("ui", mode="before")
    @classmethod
    def lower(cls, value: str) -> str:
        return value.lower()


def _check_mutually_exclusive(group: Iterable[Any], msg: str) -> None:
    if sum(1 for value in group if value) >= 2:
        raise ValueError(msg)
