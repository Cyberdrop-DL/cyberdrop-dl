from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Literal, overload, override

from pydantic import BaseModel
from typing_extensions import TypeVar

from cyberdrop_dl import aio, signature
from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.kemono.models import Creator, Post, User, UserPostModel
from cyberdrop_dl.utils.dataclass import deserialize

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Mapping

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


UserPostT = TypeVar("UserPostT", bound=BaseModel)


class KemonoAPI(API, Generic[UserPostT]):  # noqa: UP046
    ENTRYPOINT: ClassVar[AbsoluteHttpURL]
    CDN: ClassVar[AbsoluteHttpURL]
    VALID_QUERY_PARAMS: ClassVar[set[str]] = {"o", "q", "tags", "order", "sort"}
    __post__: type[UserPostT] = UserPostModel  # pyright: ignore[reportAssignmentType]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        assert cls.ENTRYPOINT
        super().__init_subclass__(**kwargs)

    def __post_init__(self) -> None:
        self.creator: CreatorEndpoint[UserPostT] = CreatorEndpoint(self)
        self.account: AccountEndpoint[UserPostT] = AccountEndpoint(self)
        self.user_names: dict[User, str] = {}

    @override
    @signature.copy(API.request_json)
    async def request_json(self, *args, **kwargs) -> Any:  # pyright: ignore[reportMissingParameterType]
        async with self.request(*args, **kwargs) as resp:
            return await resp.json(encoding="utf-8", content_type=False)

    async def creators(self) -> dict[User, str]:
        url = self.ENTRYPOINT / "creators"
        resp: list[dict[str, Any]] = await self.request_json(url)
        if type(resp) is dict:
            resp = resp.get("creators", resp)
        return {User(u["service"], u["id"]): u["name"] for u in resp}

    async def post(self, service: str, creator_id: str, post_id: str) -> UserPostT:
        url = self.ENTRYPOINT / service / "user" / creator_id / "post" / post_id
        resp = await self.request_json(url)
        post = resp.get("post", resp)
        post.setdefault("user_id", creator_id)
        post.setdefault("service", service)
        return self.__post__.model_validate(post)

    async def search(self, query: Mapping[str, str]) -> AsyncGenerator[map[UserPostT]]:
        url = self.ENTRYPOINT / "posts"
        query = dict(_filter_query(query, self.VALID_QUERY_PARAMS))
        assert query
        url = url.update_query(query)
        async for posts in self.pager(url):
            yield map(self.__post__.model_validate, posts)

    async def search_hash(self, file_hash: str) -> dict[str, Any]:
        url = self.ENTRYPOINT / "search_hash" / file_hash
        return await self.request_json(url)

    async def pager(
        self,
        url: AbsoluteHttpURL,
        step_size: int = 50,
        key: str = "posts",
    ) -> AsyncGenerator[list[dict[str, Any]]]:
        for offset in itertools.count(int(url.query.get("o") or 0), step_size):
            data = await self.request_json(url.update_query(o=offset))
            if key and type(data) is dict:
                data = data.get(key, data)
            if not data:
                break
            count = len(data)
            yield data
            if count < step_size:
                break


class AccountEndpoint(API.Endpoint[KemonoAPI[UserPostT]]):
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


class CreatorEndpoint(API.Endpoint[KemonoAPI[UserPostT]]):
    @override
    def __post_init__(self) -> None:
        self._locks: aio.WeakAsyncLocks[User] = aio.WeakAsyncLocks()

    async def __getitem__(self, user: User) -> str:
        try:
            return self.api.user_names[user]
        except KeyError:
            async with self._locks[user]:
                creator = await self.profile(user.service, user.id)
                self.api.user_names[user] = creator.name
                return creator.name

    async def profile(self, service: str, creator_id: str) -> Creator:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "profile"
        resp = await self.api.request_json(url)
        return Creator.model_validate(resp)

    async def posts(
        self, service: str, creator_id: str, query: Mapping[str, str] | None = None
    ) -> AsyncGenerator[map[UserPostT]]:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "posts"
        if query:
            url = url.update_query(dict(_filter_query(query, self.api.VALID_QUERY_PARAMS)))

        def parse(post: dict[str, Any]):
            post.setdefault("user_id", creator_id)
            post.setdefault("service", service)
            return self.api.__post__.model_validate(post)

        async for posts in self.api.pager(url):
            yield map(parse, posts)


def _filter_query(query: Mapping[str, str], params: set[str]) -> Generator[tuple[str, str]]:
    for name, value in query.items():
        if value and name in params:
            yield name, value
