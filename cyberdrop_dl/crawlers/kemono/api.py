from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl import signature
from cyberdrop_dl.cache import cached_method
from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.kemono.models import User, UserPost

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


class KemonoAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL]  # = AbsoluteHttpURL("https://pawchive.pw/api/v1")

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        assert cls.ENTRYPOINT

    def __post_init__(self) -> None:
        self.posts_w_ads: list[str] = []
        self.post: PostEndpoint = PostEndpoint(self)
        self.creator: CreatorEndpoint = CreatorEndpoint(self)
        self.account: AccountEndpoint = AccountEndpoint(self)

    @override
    @signature.copy(API.request_json)
    async def request_json(self, *args, **kwargs) -> Any:  # pyright: ignore[reportMissingParameterType]
        async with self.request(*args, **kwargs) as resp:
            return await resp.json(encoding="utf-8", content_type=False)

    @cached_method(ttl=3600)
    async def creators(self) -> dict[User, str]:
        url = self.ENTRYPOINT / "creators"
        resp: list[dict[str, Any]] = await self.request_json(url)
        return {User(u["service"], u["id"]): u["name"] for u in resp}

    async def search(
        self, offset: int = 0, query: str | None = None, tags: str | None = None
    ) -> AsyncGenerator[map[UserPost]]:
        url = self.ENTRYPOINT / "posts"
        async for posts in self.pager(url.update_query(q=query or "", o=offset, tag=tags or "")):
            yield map(UserPost.model_validate, posts)

    async def search_hash(self, file_hash: str):
        url = self.ENTRYPOINT / "search_hash" / file_hash
        return await self.request_json(url)

    async def pager(
        self,
        url: AbsoluteHttpURL,
        step_size: int = 50,
        key: str | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]]]:
        for offset in itertools.count(int(url.query.get("o") or 0), step_size):
            data = await self.request_json(url.update_query(o=offset))
            if key is not None:
                data = data[key]
            if not data:
                break
            count = len(data)
            yield data
            if count < step_size:
                break


class KemonoAPIEndpoint:
    api: KemonoAPI

    def __init__(self, api: KemonoAPI) -> None:
        self.api = api

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


class AccountEndpoint(KemonoAPIEndpoint):
    async def favorites(self, type: str):  # noqa: A002
        url = self.api.ENTRYPOINT / "account/favorites"
        return await self.api.request_json(url.update_query(type=type))


class CreatorEndpoint(KemonoAPIEndpoint):
    async def announcements(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "announcements"
        return await self.api.request_json(url)

    async def dms(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "dms"
        return await self.api.request_json(url)

    async def fancards(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "fancards"
        return await self.api.request_json(url)

    async def profile(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "profile"
        return await self.api.request_json(url)

    async def links(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "links"
        return await self.api.request_json(url)

    async def tags(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "tags"
        return await self.api.request_json(url)

    async def posts(
        self, service: str, creator_id: str, offset: int = 0, query: str | None = None, tags: str | None = None
    ) -> AsyncGenerator[map[UserPost]]:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "posts"
        _params = {"o": offset, "tag": tags, "q": query}
        async for posts in self.api.pager(url):
            yield map(UserPost.model_validate, posts)

    async def gather_ads(self, service: str, creator_id: str) -> None:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "posts"
        async for posts in self.api.pager(url):
            self.api.posts_w_ads.extend(p["id"] for p in posts)


class PostEndpoint(KemonoAPIEndpoint):
    async def __call__(self, service: str, creator_id: str, post_id: str) -> UserPost:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "post" / post_id
        resp = await self.api.request_json(url)
        return UserPost.model_validate(resp["post"])

    async def comments(self, service: str, creator_id: str, post_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "post" / post_id / "comments"
        return await self.api.request_json(url)

    async def revisions(self, service: str, creator_id: str, post_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "post" / post_id / "revisions"
        return await self.api.request_json(url)
