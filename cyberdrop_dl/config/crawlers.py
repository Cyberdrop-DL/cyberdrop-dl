from pydantic import Field

from cyberdrop_dl.models import ConfigGroup, ConfigModel
from cyberdrop_dl.models.types import FalsyAsTuple, HttpURL, NonEmptyStr, RemoveDuplicates


class KemonoConfig(ConfigModel):
    ignore_ads: bool = False
    "Ignore advertisement posts"
    ignore_post_content: bool = True
    "Ignore URL in inside the content (text) of posts"


class TikTokConfig(ConfigModel):
    original: bool = False
    "Download videos in original quality (slower)"


class GenericCrawlers(ConfigModel):
    wordpress_media: FalsyAsTuple[HttpURL] = ()
    wordpress_html: FalsyAsTuple[HttpURL] = ()
    discourse: FalsyAsTuple[HttpURL] = ()
    chevereto: FalsyAsTuple[HttpURL] = ()


class Crawlers(ConfigGroup, name=None):
    disabled: RemoveDuplicates[FalsyAsTuple[NonEmptyStr]] = ()
    "Name of crawlers to disable for the current run"

    generic: GenericCrawlers = Field(default_factory=GenericCrawlers)
    kemono: KemonoConfig = Field(default_factory=KemonoConfig)
    coomer: KemonoConfig = Field(default_factory=KemonoConfig)
    nekohouse: KemonoConfig = Field(default_factory=KemonoConfig)
    tiktok: TikTokConfig = Field(default_factory=TikTokConfig)
