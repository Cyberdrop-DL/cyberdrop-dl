from typing import Annotated

from pydantic import AfterValidator, Field

from cyberdrop_dl.models import AliasModel, ConfigGroup
from cyberdrop_dl.models.types import ListNonEmptyStr


def _unique_list[T](value: list[T]) -> list[T]:
    return sorted(set(value))  # pyright: ignore[reportArgumentType, reportUnknownVariableType]


class KemonoConfig(AliasModel):
    ignore_ads: bool = False
    ignore_post_content: bool = True


class TiktokConfig(AliasModel):
    original: bool = False


class Crawlers(ConfigGroup):
    disabled: Annotated[ListNonEmptyStr, AfterValidator(_unique_list)] = Field(default_factory=list)
    kemono: KemonoConfig = Field(default_factory=KemonoConfig)
    coomer: KemonoConfig = Field(default_factory=KemonoConfig)
    nekohouse: KemonoConfig = Field(default_factory=KemonoConfig)
    tiktok: TiktokConfig = Field(default_factory=TiktokConfig)
