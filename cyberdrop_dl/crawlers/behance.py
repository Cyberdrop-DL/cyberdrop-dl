from __future__ import annotations

import re
import uuid
from typing import Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css, json
from cyberdrop_dl.utils.utilities import error_handling_wrapper

SCRIPT_SELECTOR = "script#beconfig-store_state"
BCP_VALUE = str(uuid.uuid4())
GRAPHQL_URL = AbsoluteHttpURL("https://www.behance.net/v3/graphql/")
GRAPHQL_QUERIES = {
    "GetProfileProjects": """
        query GetProfileProjects($username: String, $after: String) {
            user(username: $username) {
                profileProjects(first: 20, after: $after) {
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                    nodes {
                        isPrivate
                        url
                    }
                }
            }
        }
    """,
}
GRAPHQL_HEADERS = {
    "Content-Type": "application/json",
    "X-BCP": BCP_VALUE,
    "X-Requested-With": "XMLHttpRequest",
}


class BehanceCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Gallery": "/gallery/<gallery_id>/<gallery_name>",
        "Image": "/gallery/<gallery_id>/<gallery_name>/modules/<module_id>",
        "Profile": "/<user_name>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.behance.net")
    DOMAIN: ClassVar[str] = "behance.net"
    FOLDER_DOMAIN: ClassVar[str] = "Behance"

    def _check_access_token(self) -> None:
        if token := self.manager.config_manager.authentication_data.behance.access_token:
            self.update_cookies({"iat0": token})

    @error_handling_wrapper
    async def _load_initial_cookies(self, url) -> None:
        await self.request_soup(url, impersonate=True)
        self.update_cookies({"originalReferrer": "", "ilo0": "true", "ilo1": "true", "bcp": BCP_VALUE})
        self._check_access_token()

    async def async_startup(self) -> None:
        await self._load_initial_cookies(self.PRIMARY_URL)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["gallery", gallery_id, _, "modules", _]:
                return await self.image(scrape_item)
            case ["gallery", gallery_id, _]:
                return await self.gallery(scrape_item, gallery_id)
            case [user_name]:
                return await self.profile(scrape_item, user_name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, gallery_id: str) -> None:
        results = await self.get_album_results(gallery_id)

        soup = await self.request_soup(scrape_item.url)
        gallery_data = css.select_text(soup, SCRIPT_SELECTOR)
        gallery_data = json.loads(gallery_data)["project"]["project"]
        if gallery_data["matureAccess"] != "allowed":
            raise ScrapeError(401, "This gallery contains mature content and need an access_token to access.")

        title = self.create_title(gallery_data["name"], gallery_id)
        scrape_item.setup_as_album(title, album_id=gallery_id)

        for module in gallery_data["allModules"]:
            if module["__typename"] == "ImageModule":
                self._process_image_module(scrape_item, module, results)
            elif module["__typename"] == "MediaCollectionModule":
                self._process_media_collection(scrape_item, module, results)

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return
        soup = await self.request_soup(scrape_item.url)
        module_data = css.select_text(soup, SCRIPT_SELECTOR)
        module_data = json.loads(module_data)["projectModule"]["projectModule"]
        src_url = self._replace_src_url(module_data["imageSizes"]["size_disp"]["url"])
        await self.direct_file(scrape_item, src_url)

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem, user_name: str) -> None:
        title = self.create_title(user_name)
        scrape_item.setup_as_profile(title)

        pagination_cursor = None
        hasNextPage = True
        request_body = {
            "query": GRAPHQL_QUERIES["GetProfileProjects"],
            "variables": {"username": user_name, "after": pagination_cursor},
        }
        while hasNextPage:
            response = await self.request_json(
                GRAPHQL_URL,
                method="POST",
                json=request_body,
                headers=GRAPHQL_HEADERS,
            )
            profile_projects = response["data"]["user"]["profileProjects"]
            # Set up for next page if any
            pagination_cursor = profile_projects["pageInfo"]["endCursor"]
            hasNextPage = profile_projects["pageInfo"]["hasNextPage"]
            request_body["variables"]["after"] = pagination_cursor

            for project in profile_projects["nodes"]:
                if project["isPrivate"]:
                    continue
                project_url = self.parse_url(project["url"])
                new_scrape_item = scrape_item.create_child(project_url)
                self.create_task(self.run(new_scrape_item))
                scrape_item.add_children()

    def _replace_src_url(self, url: str) -> AbsoluteHttpURL:
        return self.parse_url(re.sub(r"/project_modules/([^/]+)/", "/project_modules/source/", url))

    def _process_media_collection(
        self, scrape_item: ScrapeItem, module: dict[str, Any], results: dict[str, int]
    ) -> None:
        for component in module["components"]:
            src_url = self._replace_src_url(component["imageSizes"]["allAvailable"][0]["url"])
            if results and self.check_album_results(src_url, results):
                continue
            new_scrape_item = scrape_item.create_child(src_url)
            self.create_task(self.direct_file(new_scrape_item))
            scrape_item.add_children()

    def _process_image_module(self, scrape_item: ScrapeItem, module: dict[str, Any], results: dict[str, int]) -> None:
        module_url = scrape_item.url / "modules" / str(module["id"])
        src_url = self._replace_src_url(module["imageSizes"]["allAvailable"][0]["url"])
        if results and self.check_album_results(module_url, results):
            return
        new_scrape_item = scrape_item.create_child(module_url)
        self.create_task(self.direct_file(new_scrape_item, src_url))
        scrape_item.add_children()
