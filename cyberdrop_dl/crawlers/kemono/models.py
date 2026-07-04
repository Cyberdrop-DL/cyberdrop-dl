import datetime
from collections.abc import Generator
from typing import Annotated, NamedTuple, override

from pydantic import BeforeValidator, Field

from cyberdrop_dl.models import DeferredModel
from cyberdrop_dl.models.validators import falsy_as, falsy_as_none


class User(NamedTuple):
    service: str
    id: str


class File(NamedTuple):
    path: str
    name: str | None = None  # Sometimes present
    server: str | None = None  # Sometimes present in attachments


class Embed(NamedTuple):
    url: str
    subject: str
    description: str


class Post(DeferredModel):
    id: str
    content: str = ""
    file: Annotated[File | None, BeforeValidator(falsy_as_none)] = None
    attachments: tuple[File, ...] = ()
    published: datetime.datetime | None = None
    added: datetime.datetime | None = None
    edited: datetime.datetime | None = None
    timestamp: int | None = None
    tags: Annotated[tuple[str, ...], BeforeValidator(lambda x: falsy_as(x, ()))] = ()
    embed: Annotated[Embed | None, BeforeValidator(falsy_as_none)] = None

    @override
    def model_post_init(self, *_: object) -> None:
        if date := self.published or self.added:
            self.timestamp = int(date.timestamp())

    @property
    def all_files(self) -> Generator[File]:
        if self.file:
            yield self.file
        yield from self.attachments


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
