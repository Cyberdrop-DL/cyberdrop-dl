from typing import Annotated, Literal

from pydantic import Field
from pydantic.functional_validators import AfterValidator

from cyberdrop_dl.models import ConfigGroup, ConfigModel
from cyberdrop_dl.models.types import HttpURL, NonEmptyStr
from cyberdrop_dl.models.validators import remove_duplicates


class KemonoConfig(ConfigModel):
    file: bool = True
    "Download the main file in a post (if any)"

    attachments: bool = True
    "Download all attachments in a post (may or may not include `file`)"

    content_urls: bool = True
    "Download any URL found inside the description (text) of a post (slower)"

    embed: bool = True
    "Download the embedded file from third party sites (if any)(mega.nz, pcloud, dropbox, etc..)"


class TikTokConfig(ConfigModel):
    original: bool = False
    "Download videos in original quality (slower)"


class BandcampConfig(ConfigModel):
    formats: Annotated[
        tuple[Literal["mp3-320", "mp3", "aac-hi", "wav", "flac", "vorbis", "aiff", "alas"], ...],
        AfterValidator(remove_duplicates),
    ] = (
        "mp3-320",
        "mp3",
        "aac-hi",
        "wav",
        "flac",
        "vorbis",
        "aiff",
        "alas",
    )
    "Format to choose for downloads (if available), ordered by preference"


class ClypitConfig(ConfigModel):
    prefer_mp3: bool = False
    """Download audios as .mp3 files even if WAV (high quality) versions are available"""


class OnePaceConfig(ConfigModel):
    prefer_dub: bool = False
    """Download episodes with english audio tracks instead of japanese (if available)"""


class GenericCrawlers(ConfigModel):
    wordpress_media: tuple[HttpURL, ...] = ()
    wordpress_html: tuple[HttpURL, ...] = ()
    discourse: tuple[HttpURL, ...] = ()
    chevereto: tuple[HttpURL, ...] = ()
    kvs: tuple[HttpURL, ...] = ()


class Crawlers(ConfigGroup, name=None):
    disabled: set[NonEmptyStr] = Field(default_factory=set)
    "Name of crawlers to disable for the current run"

    bandcamp: BandcampConfig = Field(default_factory=BandcampConfig)
    clypit: ClypitConfig = Field(default_factory=ClypitConfig)
    generic: GenericCrawlers = Field(default_factory=GenericCrawlers)
    one_pace: OnePaceConfig = Field(default_factory=OnePaceConfig)
    tiktok: TikTokConfig = Field(default_factory=TikTokConfig)
    pawchive: KemonoConfig = Field(default_factory=KemonoConfig)
