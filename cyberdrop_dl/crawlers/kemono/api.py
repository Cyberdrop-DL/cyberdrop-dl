from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, ClassVar, Literal, overload, override

from cyberdrop_dl import signature
from cyberdrop_dl.cache import cached_method
from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.kemono.models import Post, User, UserPostModel
from cyberdrop_dl.utils.dataclass import deserialize

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Mapping

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


VALID_QUERY_PARAMS = {"o", "q", "tags", "order", "sort"}


class KemonoAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        assert cls.ENTRYPOINT
        super().__init_subclass__(**kwargs)

    def __post_init__(self) -> None:
        self.post: PostEndpoint = PostEndpoint(self)
        self.creator: CreatorEndpoint = CreatorEndpoint(self)
        self.account: AccountEndpoint = AccountEndpoint(self)

    @override
    @signature.copy(API.request_json)
    async def request_json(self, *args, **kwargs) -> Any:  # pyright: ignore[reportMissingParameterType]
        async with self.request(*args, **kwargs) as resp:
            return await resp.json(encoding="utf-8", content_type=False)

    @cached_method(ttl=1800)
    async def creators(self) -> dict[User, str]:
        url = self.ENTRYPOINT / "creators"
        resp: list[dict[str, Any]] = await self.request_json(url)
        return {User(u["service"], u["id"]): u["name"] for u in resp}

    async def search(self, query: Mapping[str, str]) -> AsyncGenerator[map[UserPostModel]]:
        url = self.ENTRYPOINT / "posts"
        query = dict(_filter_query(query))
        assert query
        url = url.update_query(query)
        async for posts in self.pager(url):
            yield map(UserPostModel.model_validate, posts)

    async def search_hash(self, file_hash: str) -> dict[str, Any]:
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
            if key:
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
    @overload
    async def favorites(self, type_: Literal["post"]) -> AsyncGenerator[map[Post]]: ...

    @overload
    async def favorites(self, type_: Literal["artist"]) -> AsyncGenerator[map[User]]: ...

    async def favorites(
        self, type_: Literal["artist", "post"]
    ) -> AsyncGenerator[map[Post]] | AsyncGenerator[map[User]]:
        url = self.api.ENTRYPOINT / "account/favorites"
        cls_ = User if type_ == "artist" else Post

        def parse(item: dict[str, Any]):
            return deserialize(cls_, item)

        async for page in self.api.pager(url):
            yield map(parse, page)  # pyright: ignore[reportReturnType]


class CreatorEndpoint(KemonoAPIEndpoint):
    async def profile(self, service: str, creator_id: str) -> dict[str, Any]:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "profile"
        return await self.api.request_json(url)

    async def links(self, service: str, creator_id: str) -> dict[str, Any]:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "links"
        return await self.api.request_json(url)

    async def tags(self, service: str, creator_id: str) -> dict[str, Any]:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "tags"
        return await self.api.request_json(url)

    async def posts(
        self, service: str, creator_id: str, query: Mapping[str, str] | None = None
    ) -> AsyncGenerator[map[UserPostModel]]:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "posts"
        if query:
            url = url.update_query(dict(_filter_query(query)))

        async for posts in self.api.pager(url):
            yield map(UserPostModel.model_validate, posts)


class PostEndpoint(KemonoAPIEndpoint):
    async def __call__(self, service: str, creator_id: str, post_id: str) -> UserPostModel:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "post" / post_id
        resp = await self.api.request_json(url)
        return UserPostModel.model_validate(resp.get("post", resp))

    async def comments(self, service: str, creator_id: str, post_id: str) -> dict[str, Any]:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "post" / post_id / "comments"
        return await self.api.request_json(url)

    async def revisions(self, service: str, creator_id: str, post_id: str) -> dict[str, Any]:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "post" / post_id / "revisions"
        return await self.api.request_json(url)


def _filter_query(query: Mapping[str, str]) -> Generator[tuple[str, str]]:
    for name, value in query.items():
        if value and name in VALID_QUERY_PARAMS:
            yield name, value
