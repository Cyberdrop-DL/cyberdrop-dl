from __future__ import annotations

import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


GRAPHQL_QUERIES = {
    "AlbumGet": "query AlbumGet($id: ID!) {\n  album {\n    get(id: $id) {\n      ... on Album {\n        ...AlbumStandard\n      }\n      ... on MutationError {\n        errors {\n          code\n          message\n        }\n      }\n    }\n  }\n}\n    \n    fragment AlbumStandard on Album {\n  __typename\n  id\n  title\n  labels\n  description\n  created\n  modified\n  like_status\n  number_of_favorites\n  number_of_dislikes\n  moderation_status\n  marked_for_deletion\n  marked_for_processing\n  number_of_pictures\n  number_of_animated_pictures\n  number_of_duplicates\n  slug\n  is_manga\n  url\n  download_url\n  permissions\n  created_by {\n    id\n    url\n    name\n    display_name\n    user_title\n    avatar_url\n  }\n  content {\n    id\n    title\n    url\n  }\n  language {\n    id\n    title\n    url\n  }\n  tags {\n    category\n    text\n    url\n    count\n  }\n  genres {\n    id\n    title\n    slug\n    url\n  }\n  audiences {\n    id\n    title\n    url\n  }\n  is_featured\n  featured_date\n  featured_by {\n    id\n    url\n    name\n    display_name\n    user_title\n    avatar_url\n  }\n}",
    "AlbumListOwnPictures": "query AlbumListOwnPictures($input: PictureListInput!) {\n    picture {\n        list(input: $input) {\n            info {\n                ...FacetCollectionInfo\n            }\n            items {\n                ...PictureStandardWithoutAlbum\n            }\n        }\n    }\n}\n\nfragment FacetCollectionInfo on FacetCollectionInfo {\n    page\n    has_next_page\n    has_previous_page\n    total_items\n    total_pages\n    items_per_page\n    url_complete\n    url_filters_only\n}\n\nfragment PictureStandardWithoutAlbum on Picture {\n    __typename\n    id\n    title\n    created\n    like_status\n    number_of_comments\n    number_of_favorites\n    status\n    width\n    height\n    resolution\n    aspect_ratio\n    url_to_original\n    url_to_video\n    is_animated\n    position\n    tags {\n        id\n        category\n        text\n        url\n    }\n    permissions\n    url\n    thumbnails {\n        width\n        height\n        size\n        url\n    }\n}",
    "PictureListInsideAlbum": "query PictureListInsideAlbum($input: PictureListInput!) {\n  picture {\n    list(input: $input) {\n      info {\n        ...FacetCollectionInfo\n      }\n      items {\n        __typename\n        id\n        title\n        description\n        created\n        like_status\n        number_of_comments\n        number_of_favorites\n        moderation_status\n        width\n        height\n        resolution\n        aspect_ratio\n        url_to_original\n        url_to_video\n        is_animated\n        position\n        permissions\n        url\n        tags {\n          category\n          text\n          url\n        }\n        thumbnails {\n          width\n          height\n          size\n          url\n        }\n      }\n    }\n  }\n}\n    \n    fragment FacetCollectionInfo on FacetCollectionInfo {\n  page\n  has_next_page\n  has_previous_page\n  total_items\n  total_pages\n  items_per_page\n  url_complete\n}",
    "AlbumListWithPeek": "query AlbumListWithPeek($input: AlbumListInput!) {\n    album {\n        list(input: $input) {\n            info {\n                ...FacetCollectionInfo\n            }\n            items {\n                ...AlbumMinimal\n                peek_thumbnails {\n                    width\n                    height\n                    size\n                    url\n                }\n            }\n        }\n    }\n}\n\nfragment FacetCollectionInfo on FacetCollectionInfo {\n    page\n    has_next_page\n    has_previous_page\n    total_items\n    total_pages\n    items_per_page\n    url_complete\n    url_filters_only\n}\n\nfragment AlbumMinimal on Album {\n    __typename\n    id\n    title\n    labels\n    description\n    created\n    modified\n    number_of_favorites\n    number_of_pictures\n    slug\n    is_manga\n    url\n    download_url\n    cover {\n        width\n        height\n        size\n        url\n    }\n    content {\n        id\n        title\n        url\n    }\n    language {\n        id\n        title\n        url\n    }\n    tags {\n        id\n        category\n        text\n        url\n        count\n    }\n    genres {\n        id\n        title\n        slug\n        url\n    }\n    audiences {\n        id\n        title\n        url\n    }\n}",
}


class LusciousCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/albums/<name>_<album_id>",
        "Search": "/albums/list?tagged=<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://members.luscious.net")
    DOMAIN: ClassVar[str] = "luscious"

    def __post_init__(self) -> None:
        self.api: LusciousAPI = LusciousAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["albums", slug] if album_id := slug.partition("_")[-1]:
                await self.album(scrape_item, album_id)
            case ["albums", "list"] if query := scrape_item.url.query.get("tagged"):
                await self.search(scrape_item, query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        results = await self.get_album_results(album_id)
        album = await self.api.album(album_id)
        scrape_item.setup_as_album(self.create_title(album.title, album.id), album_id=album.id)

        async for images in self.api.album_images(album.id, scrape_item.url.query):
            for album in images:
                src = self.parse_url(album["url_to_original"])
                if not self.check_album_results(src, results):
                    filename, ext = self.get_filename_and_ext(src.name)
                    await self.handle_file(src, scrape_item, filename, ext)
                scrape_item.add_children()

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        scrape_item.setup_as_forum(f"{query} [search]")
        async for results in self.api.album_list(scrape_item.url.query):
            for album in results:
                album_url = self.parse_url(album["url"])
                self.create_task(self.run(scrape_item.create_child(album_url)))
                scrape_item.add_children()


class LusciousAPI(API):
    GRAPHQL_ENDPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://members.luscious.net/graphql/nobatch/")

    def __post_init__(self) -> None:
        self._request_id = itertools.count(1).__next__

    def _query(
        self,
        name: str,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": self._request_id(),
            "operationName": name,
            "query": query,
            "variables": variables,
        }

    async def request_gql(self, operation: str, query: dict[str, Any]) -> dict[str, Any]:
        api_url = self.GRAPHQL_ENDPOINT.with_query(operationName=operation)
        resp = await self.request_json(api_url, method="POST", json=query)
        return resp["data"]

    async def album(self, album_id: str) -> Album:
        resp = await self.request_gql(
            operation := "AlbumGet",
            self._query(operation, ALBUM_QUERY, {"id": album_id}),
        )
        return deserialize(Album, resp["album"]["get"])

    def album_images(self, album_id: str, query: Mapping[str, str]):
        filters: list[dict[str, Any]] = [{"name": "album_id", "value": album_id}]
        if query.get("only_animated"):
            filters.append({"name": "is_animated", "value": 1})

        return self._pager(
            "PictureListInsideAlbum",
            ALBUM_IMAGES_QUERY,
            display=query.get("sorting", "position"),
            filters=filters,
            key="picture",
            init_page=int(query.get("page", 1)),
        )

    def album_list(self, query: Mapping[str, str]):
        filters = [{"name": i, "value": v} for i, v in query.items() if i not in {"page", "display", "q"}]
        return self._pager(
            "PictureListInsideAlbum",
            ALBUM_IMAGES_QUERY,
            display=query.get("display", "date_newest"),
            filters=filters,
            key="album",
            init_page=int(query.get("page", 1)),
        )

    async def _pager(  # noqa: PLR0913
        self,
        operation: str,
        query: str,
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
                    "items_per_page": 50,
                    "page": page,
                },
            }
            resp = await self.request_gql(operation, self._query(operation, query, variables))
            results = resp[key]["list"]
            yield results["items"]
            if not results["info"]["has_next_page"]:
                break


@dataclasses.dataclass(slots=True)
class Album:
    id: str
    title: str
    description: str
    created: float


ALBUM_QUERY = """
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

ALBUM_IMAGES_QUERY = """
query PictureListInsideAlbum($input: PictureListInput!) {
  picture {
    list(input: $input) {
      info {
        ...FacetCollectionInfo
      }
      items {
        __typename
        id
        title
        description
        created
        like_status
        number_of_comments
        number_of_favorites
        moderation_status
        width
        height
        resolution
        aspect_ratio
        url_to_original
        url_to_video
        is_animated
        position
        permissions
        url
        tags {
          category
          text
          url
        }
        thumbnails {
          width
          height
          size
          url
        }
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
"""
