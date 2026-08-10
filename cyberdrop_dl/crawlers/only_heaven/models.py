import dataclasses
from pathlib import Path
from typing import Any, override

from pydantic import Field
from pydantic.aliases import AliasChoices

from cyberdrop_dl.crawlers.kemono.models import User
from cyberdrop_dl.models import DeferredModel
from cyberdrop_dl.models.types import AwareDatetime


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class Variant:
    bytes: int
    name: str


@dataclasses.dataclass(slots=True, frozen=True)
class File:
    id: str
    sha256: str
    kind: str
    mimeType: str  # noqa: N815
    width: int
    height: int
    storageKey: str  # noqa: N815
    variants: tuple[Variant, ...]
    originalFilename: str | None = None  # noqa: N815, missing on search results

    @property
    def name(self) -> str:
        if self.originalFilename:
            return self.originalFilename
        ext = Path(max(self.variants).name).suffix
        return self.storageKey + ext


class PostModel(DeferredModel, val_temporal_unit="seconds", extra="ignore"):
    id: str
    content: str | None = Field(validation_alias=AliasChoices("caption", "captionHtml"), default=None)
    attachments: tuple[File, ...] = ()
    published: AwareDatetime | None = None
    added: AwareDatetime | None = None
    timestamp: int | None = None
    links: tuple[Any, ...] = ()
    tags: tuple[str, ...] = ()
    preview_state: str | None = None
    has_full: bool = True
    file: File | None = None
    user_name: str | None = Field(validation_alias="creatorName", default=None)

    @override
    def model_post_init(self, *_: object) -> None:
        if date := self.published or self.added:
            self.timestamp = int(date.timestamp())


class UserPostModel(PostModel):
    service: str
    user_id: str = Field(validation_alias="creatorId")
    title: str | None = None

    @property
    def user(self) -> User:
        return User(self.service, self.user_id)

    @property
    def web_path_qs(self) -> str:
        return f"creators/{self.service}/{self.user_id}/post/{self.id}"
