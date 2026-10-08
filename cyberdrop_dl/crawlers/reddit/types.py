# https://github.com/ArthurHeitmann/arctic_shift/blob/1565f3456488a99c212166e5779dc0b87f622ad3/schemas/RS.ts
from __future__ import annotations

import dataclasses
from typing import Any, ClassVar, Literal, NotRequired, Self, TypedDict

from cyberdrop_dl.utils.dataclass import fields_names


class Meta(TypedDict, total=False):
    note: str
    removal_type: Literal[
        "deleted",
        "moderator",
        "reddit",
        "automod_filtered",
        "content_takedown",
        "author",
        "copyright_takedown",
        "community_ops",
        "anti_evil_ops",
        "trademark_takedown",
    ]


class Oembed(TypedDict, total=False):
    author_name: str
    author_url: str
    height: int
    html: str
    provider_name: str
    provider_url: str
    thumbnail_height: int
    thumbnail_url: str
    thumbnail_width: int
    title: str
    type: Literal["video"]
    version: Literal["1.0"]
    width: int


class RedditVideo(TypedDict):
    bitrate_kbps: int
    dash_url: str
    duration: int
    fallback_url: str
    has_audio: NotRequired[bool]
    height: int
    hls_url: str
    is_gif: bool
    scrubber_media_url: str
    transcoding_status: Literal["completed"]
    width: int


class GalleryItem(TypedDict):
    caption: NotRequired[str]
    id: int
    media_id: str


class RedditGallery(TypedDict):
    items: list[GalleryItem]


@dataclasses.dataclass(slots=True, frozen=True)
class RedditObj:
    _prefix: ClassVar[str]

    @classmethod
    def parse(cls, post: Submission) -> Self:
        data = {key: post.pop(f"{cls._prefix}_{key}", None) for key in fields_names(cls)}
        data["name"] = post.get(cls._prefix)
        return cls(**data)


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class Subreddit(RedditObj):
    _prefix: ClassVar[str] = "subreddit"
    id: str
    name: str
    name_prefixed: str
    type: Literal["public", "user", "restricted"]


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class Author(RedditObj):
    _prefix: ClassVar[str] = "author"
    name: str
    fullname: str | None
    premium: bool | None


class Submission(TypedDict):
    _meta: Meta
    author: Author
    created_utc: int
    domain: str
    subreddit: Subreddit
    id: str
    media: NotRequired[Oembed | RedditVideo | None]
    media_only: bool
    name: str
    over_18: bool
    permalink: str
    media_metadata: NotRequired[dict[str, dict[str, Any]]]
    post_hint: NotRequired[Literal["image", "link", "rich:video", "self", "hosted:video"]]
    score: int
    secure_media: NotRequired[Oembed | RedditVideo | None]
    selftext: str
    title: str
    ups: int
    upvote_ratio: int
    url: str
    url_overridden_by_dest: NotRequired[str]
    gallery_data: NotRequired[RedditGallery]
    selftext_html: NotRequired[str]
