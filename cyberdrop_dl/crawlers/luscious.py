from __future__ import annotations

import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import LoginError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import parse_url
from cyberdrop_dl.utils.dataclass import Deserializer
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


class LusciousCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": (
            "/albums/<name>_<album_id>",
            "/albums/<name>_<album_id>?only_animated=true",
        ),
        "Search": "/albums/list?tagged=<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://members.luscious.net")
    DOMAIN: ClassVar[str] = "luscious"

    def __post_init__(self) -> None:
        self.api: LusciousAPI = LusciousAPI.from_crawler(self)

    @override
    async def __async_post_init__(self) -> None:
        with self.catch_errors(self.api.GRAPHQL_ENDPOINT), self.disable_on_error("Unable to get account credentials"):
            try:
                cookie_name = next(c for c in self.cookies.raw if c.startswith("sessionid"))
            except StopIteration:
                raise LoginError("No session ID found in cookies. Use --cookies to provide logged in cookies") from None
            else:
                self.log.debug("Session id cookie name: %s", cookie_name)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["albums", "list"] if query := scrape_item.url.query.get("tagged"):
                await self.search(scrape_item, query)
            case ["albums", slug] if album_id := slug.partition("_")[-1]:
                await self.album(scrape_item, album_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        album = await self.api.album(album_id)
        await self._album(scrape_item, album)

    @error_handling_wrapper
    async def _album(self, scrape_item: ScrapeItem, album: Album) -> None:
        scrape_item.setup_as_album(self.create_title(album.title, album.id), album_id=album.id)
        results = await self.get_album_results(album.id)

        async for pictures in self.api.album_pictures(album.id, scrape_item.url.query):
            for pic in pictures:
                if self.check_album_results(pic.url_to_original, results):
                    continue

                self.create_eager_task(self._picture(scrape_item.copy(), pic))
                scrape_item.add_children()

    async def _picture(self, scrape_item: ScrapeItem, pic: Picture) -> None:
        scrape_item.url = pic.url
        scrape_item.uploaded_at = pic.created
        await self.direct_file(scrape_item, pic.url_to_original)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        scrape_item.setup_as_forum(f"{query} [search]")
        async for albums in self.api.album_list(scrape_item.url.query):
            for album in albums:
                self.create_task(self._album(scrape_item.create_child(album.url), album))
                scrape_item.add_children()


_deserialize = Deserializer(
    converters={
        "url": lambda url: parse_url(url, LusciousCrawler.PRIMARY_URL),
        "url_to_original": parse_url,
        "url_to_video": lambda url: url and parse_url(url),
    },
)


@dataclasses.dataclass(slots=True)
class Album:
    id: str
    title: str
    description: str
    created: float
    url: AbsoluteHttpURL

    parse = classmethod(_deserialize)


@dataclasses.dataclass(slots=True)
class Picture:
    id: str
    created: float
    is_animated: bool
    url: AbsoluteHttpURL
    url_to_original: AbsoluteHttpURL
    url_to_video: AbsoluteHttpURL | None = None

    parse = classmethod(_deserialize)


@HTTPConfig(rate_limit=(5, 1))
class LusciousAPI(API):
    GRAPHQL_ENDPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://members.luscious.net/graphql/nobatch/")

    def __post_init__(self) -> None:
        self._request_id: Callable[[], int] = itertools.count(1).__next__

    async def request_gql(self, operation: str, variables: dict[str, Any]) -> dict[str, Any]:
        gql_url = self.GRAPHQL_ENDPOINT.with_query(operationName=operation)
        resp = await self.request_json(
            gql_url,
            method="POST",
            json={
                "id": self._request_id(),
                "operationName": operation,
                "query": globals()[operation],
                "variables": variables,
            },
        )
        return resp["data"]

    async def album(self, album_id: str) -> Album:
        resp = await self.request_gql("AlbumGet", {"id": album_id})
        return Album.parse(resp["album"]["get"])

    async def album_pictures(self, album_id: str, query: Mapping[str, str]) -> AsyncGenerator[map[Picture]]:
        filters: list[dict[str, Any]] = [{"name": "album_id", "value": album_id}]
        if query.get("only_animated") in ("true", "1"):
            filters.append({"name": "is_animated", "value": "1"})

        async for pictures in self.gql_pager(
            "AlbumListOwnPictures",
            display=query.get("sorting", "position"),
            filters=filters,
            key="picture",
            init_page=int(query.get("page", 1)),
        ):
            yield map(Picture.parse, pictures)

    async def album_list(self, query: Mapping[str, str]) -> AsyncGenerator[map[Album]]:
        filters = [
            {"name": name, "value": value}
            for name, value in query.items()
            if name and name not in {"page", "display", "q"}
        ]
        async for albums in self.gql_pager(
            "AlbumList",
            display=query.get("display", "date_newest"),
            filters=filters,
            key="album",
            init_page=int(query.get("page", 1)),
        ):
            yield map(Album.parse, albums)

    async def gql_pager(
        self,
        operation: str,
        *,
        display: str,
        filters: list[dict[str, Any]],
        key: str,
        init_page: int = 1,
    ) -> AsyncGenerator[list[dict[str, Any]]]:
        for page in itertools.count(init_page):
            variables = {
                "input": {
                    "display": display,
                    "filters": filters,
                    "page": page,
                },
            }
            resp = await self.request_gql(operation, variables)
            results = resp[key]["list"]
            yield results["items"]
            if not results["info"]["has_next_page"]:
                break


# ---Queries---

AlbumGet = """
query AlbumGet($id: ID!) {
  album {
    get(id: $id) {
      ... on Album {
        ...AlbumStandard
      }
      ... on MutationError {
        errors {
          code
          message
        }
      }
    }
  }
}

fragment AlbumStandard on Album {
  __typename
  id
  title
  labels
  description
  created
  modified
  like_status
  number_of_favorites
  number_of_dislikes
  moderation_status
  marked_for_deletion
  marked_for_processing
  number_of_pictures
  number_of_animated_pictures
  number_of_duplicates
  slug
  is_manga
  url
  download_url
  permissions
  cover {
    width
    height
    size
    url
  }
  created_by {
    id
    url
    name
    display_name
    user_title
    avatar_url
  }
  content {
    id
    title
    url
  }
  language {
    id
    title
    url
  }
  tags {
    category
    text
    url
    count
  }
  genres {
    id
    title
    url
    acts_as_warning
  }
  audiences {
    id
    title
    url
  }
  is_featured
  featured_date
  featured_by {
    id
    url
    name
    display_name
    user_title
    avatar_url
  }
}
"""

AlbumListOwnPictures = """
query AlbumListOwnPictures($input: PictureListInput!) {
    picture {
        list(input: $input) {
            info {
                ...FacetCollectionInfo
            }
            items {
                ...PictureStandardWithoutAlbum
            }
        }
    }
}

fragment FacetCollectionInfo on FacetCollectionInfo {
    page
    has_next_page
    has_previous_page
    total_items
    total_pages
    items_per_page
    url_complete
    url_filters_only
}

fragment PictureStandardWithoutAlbum on Picture {
    __typename
    id
    title
    created
    like_status
    number_of_comments
    number_of_favorites
    status
    width
    height
    resolution
    aspect_ratio
    url_to_original
    url_to_video
    is_animated
    position
    tags {
        id
        category
        text
        url
    }
    permissions
    url
    thumbnails {
        width
        height
        size
        url
    }
}
"""


AlbumList = """
query AlbumList($input: AlbumListInput!) {
  album {
    list(input: $input) {
      info {
        ...FacetCollectionInfo
      }
      items {
        ...AlbumInSearchList
      }
    }
  }
}

fragment FacetCollectionInfo on FacetCollectionInfo {
  page
  has_next_page
  has_previous_page
  total_items
  total_pages
  items_per_page
  url_complete
}

fragment AlbumInSearchList on Album {
  __typename
  id
  title
  description
  created
  modified
  like_status
  moderation_status
  number_of_favorites
  number_of_dislikes
  number_of_pictures
  number_of_animated_pictures
  number_of_duplicates
  slug
  is_manga
  url
  download_url
  labels
  permissions
  cover {
    width
    height
    size
    url
  }
  created_by {
    id
    url
    name
    display_name
    user_title
    avatar_url
  }
  language {
    id
    title
    url
  }
  tags {
    category
    text
    url
    count
  }
  genres {
    id
    title
    url
    acts_as_warning
  }
}
"""
