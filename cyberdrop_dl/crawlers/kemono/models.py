import dataclasses
import datetime
from typing import Annotated, override

from pydantic import BeforeValidator, Field

from cyberdrop_dl.models import DeferredModel
from cyberdrop_dl.models.validators import falsy_as_none


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class User:
    service: str
    id: str

    @property
    def web_path_qs(self) -> str:
        return f"{self.service}/user/{self.id}"


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class FavoritePost:
    service: str
    id: str
    user: str | None = None

    @property
    def web_path_qs(self) -> str:
        return f"{self.service}/user/{self.user}/post/{self.id}"


@dataclasses.dataclass(slots=True, frozen=True)
class File:
    path: str = ""
    name: str | None = None  # Sometimes present
    server: str | None = None  # Sometimes present in attachments
    deferred: bool = False


@dataclasses.dataclass(slots=True, frozen=True)
class Embed:
    url: str
    subject: str
    description: str


def tags_validator(tags: object) -> object:
    if not tags:
        return ()
    if type(tags) is str:
        if tags.startswith("{") and tags.endswith("}"):
            tags = tags[1:-1]
        return tags.split(",")
    return tags


class Post(DeferredModel):
    id: str
    content: str | None = None
    # search result has no content key, only "substring"

    file: Annotated[File | None, BeforeValidator(falsy_as_none)] = None
    attachments: tuple[File, ...] = ()
    published: datetime.datetime | None = None
    added: datetime.datetime | None = None
    edited: datetime.datetime | None = None
    timestamp: int | None = None
    tags: Annotated[tuple[str, ...], BeforeValidator(tags_validator)] = ()
    embed: Annotated[Embed | None, BeforeValidator(falsy_as_none)] = None
    has_full: bool = True

    @override
    def model_post_init(self, *_: object) -> None:
        if date := self.published or self.added:
            self.timestamp = int(date.timestamp())


class UserPost(Post):
    service: str
    user_id: str = Field(validation_alias="user")
    title: str

    @property
    def user(self) -> User:
        return User(self.service, self.user_id)

    @property
    def web_path_qs(self) -> str:
        return f"{self.service}/user/{self.user_id}/post/{self.id}"
