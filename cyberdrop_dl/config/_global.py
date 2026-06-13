# ruff: noqa: RUF012
import random

import aiohttp
from cyclopts import Parameter
from pydantic import (
    ByteSize,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    field_validator,
)

from cyberdrop_dl.models import AliasModel, SettingsGroup
from cyberdrop_dl.models.types import ByteSizeSerilized, ListPydanticURL
from cyberdrop_dl.models.validators import falsy_as_none, to_bytesize

MIN_REQUIRED_FREE_SPACE = to_bytesize("512MB")


class RateLimiting(SettingsGroup):
    download_attempts: PositiveInt = 2
    download_delay: NonNegativeFloat = 0.0
    download_speed_limit: ByteSizeSerilized = ByteSize(0)
    jitter: NonNegativeFloat = 0
    max_simultaneous_downloads_per_domain: PositiveInt = 5
    max_simultaneous_downloads: PositiveInt = 15
    rate_limit: PositiveFloat = 25

    connection_timeout: PositiveFloat = 15
    read_timeout: PositiveFloat | None = 300
    concurrent_segments: PositiveInt = 10
    """Allow up to `<N>` HLS segments to be downloaded concurrently"""

    @field_validator("read_timeout", mode="before")
    @classmethod
    def parse_timeouts(cls, value: object) -> object | None:
        return falsy_as_none(value)

    @property
    def curl_timeout(self) -> float | tuple[float, float]:
        if self.read_timeout is None:
            return self.connection_timeout
        return self.connection_timeout, self.read_timeout

    @property
    def aiohttp_timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(
            total=None,
            sock_connect=self.connection_timeout,
            sock_read=self.read_timeout,
        )

    @property
    def total_delay(self) -> NonNegativeFloat:
        """download_delay + jitter"""
        return self.download_delay + self.get_jitter()

    def get_jitter(self) -> NonNegativeFloat:
        """Get a random number in the range [0, self.jitter]"""
        return random.uniform(0, self.jitter)


class UIOptions(SettingsGroup):
    refresh_rate: PositiveFloat = 10.0


class GenericCrawlerInstances(SettingsGroup):
    wordpress_media: ListPydanticURL = []
    wordpress_html: ListPydanticURL = []
    discourse: ListPydanticURL = []
    chevereto: ListPydanticURL = []


@Parameter(name="*")
class GlobalSettings(AliasModel):
    rate_limiting_options: RateLimiting = Field(default_factory=RateLimiting)
    ui_options: UIOptions = Field(default_factory=UIOptions)
    generic_crawlers_instances: GenericCrawlerInstances = Field(default_factory=GenericCrawlerInstances)
