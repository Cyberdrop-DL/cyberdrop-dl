import dataclasses
import datetime
from typing import Annotated, override

from pydantic import AfterValidator, BeforeValidator, Field

from cyberdrop_dl import env
from cyberdrop_dl.models import DeferredModel
from cyberdrop_dl.models.validators import falsy_as, falsy_as_none


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class User:
    service: str
    id: str

    @property
    def web_path_qs(self) -> str:
        return f"{self.service}/user/{self.id}"


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class Post:
    service: str
    user: str
    id: str

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


def _parse_tags(tags: object) -> object:
    tags = falsy_as(tags, ())
    if type(tags) is str:
        if tags.startswith("{") and tags.endswith("}"):
            tags = tags[1:-1]
        return [t.strip('"') for t in tags.split(",")]
    return tags


def _assume_utc[T: datetime.datetime](date: T) -> T:
    if date.tzinfo is None:
        return date.replace(tzinfo=datetime.UTC)
    return date


type AwareDatetime = Annotated[datetime.datetime, AfterValidator(_assume_utc)]


class PostModel(DeferredModel, extra="allow" if env.DEBUG_MODE else "ignore"):
    id: str
    content: str | None = None  # search results has no "content" key, only "substring"

    file: Annotated[File | None, BeforeValidator(falsy_as_none)] = None
    attachments: tuple[File, ...] = ()
    published: AwareDatetime | None = None
    added: AwareDatetime | None = None
    edited: AwareDatetime | None = None
    timestamp: int | None = None
    tags: Annotated[tuple[str, ...], BeforeValidator(_parse_tags)] = ()
    embed: Annotated[Embed | None, BeforeValidator(falsy_as_none)] = None
    has_full: bool = True

    @override
    def model_post_init(self, *_: object) -> None:
        if date := self.published or self.added:
            self.timestamp = int(date.timestamp())


class UserPostModel(PostModel):
    service: str
    user_id: str = Field(validation_alias="user")
    title: str

    @property
    def user(self) -> User:
        return User(self.service, self.user_id)

    @property
    def web_path_qs(self) -> str:
        return f"{self.service}/user/{self.user_id}/post/{self.id}"
