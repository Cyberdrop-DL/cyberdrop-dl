from pydantic import Field

from cyberdrop_dl.models import AliasModel, ConfigGroup
from cyberdrop_dl.models.types import FalsyAsTuple, HttpURL, NonEmptyStr, RemoveDuplicates


class KemonoConfig(AliasModel):
    ignore_ads: bool = False
    ignore_post_content: bool = True


class TikTokConfig(AliasModel):
    original: bool = False


class GenericCrawlers(AliasModel):
    wordpress_media: FalsyAsTuple[HttpURL] = ()
    wordpress_html: FalsyAsTuple[HttpURL] = ()
    discourse: FalsyAsTuple[HttpURL] = ()
    chevereto: FalsyAsTuple[HttpURL] = ()


class Crawlers(ConfigGroup, name=None):
    disabled: RemoveDuplicates[FalsyAsTuple[NonEmptyStr]] = ()
    generic: GenericCrawlers = Field(default_factory=GenericCrawlers)
    kemono: KemonoConfig = Field(default_factory=KemonoConfig)
    coomer: KemonoConfig = Field(default_factory=KemonoConfig)
    nekohouse: KemonoConfig = Field(default_factory=KemonoConfig)
    tiktok: TikTokConfig = Field(default_factory=TikTokConfig)
