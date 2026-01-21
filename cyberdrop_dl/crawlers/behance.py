from __future__ import annotations

import uuid
from typing import ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css, json
from cyberdrop_dl.utils.utilities import error_handling_wrapper

IMAGE_SELECTOR = "img.ImageModuleContent-mainImage-IG1"
BCP_VALUE = str(uuid.uuid4())
GRAPHQL_URL = AbsoluteHttpURL("https://www.behance.net/v3/graphql/")
GRAPHQL_QUERIES = {
    "GetProfileProjects": "query GetProfileProjects($username: String, $after: String) {\n    user(username: $username) {\n      profileProjects(first: 20, after: $after) {\n        pageInfo {\n          endCursor\n          hasNextPage\n        }\n        nodes {\n          __typename\n          adminFlags {\n            mature_lock\n            privacy_lock\n            dmca_lock\n            flagged_lock\n            privacy_violation_lock\n            trademark_lock\n            spam_lock\n            eu_ip_lock\n          }\n          \n          hasMatureContent\n          id\n          isBoosted\n          isFeatured\n          isHiddenFromWorkTab\n          isMatureReviewSubmitted\n          isMonaReported\n          isOwner\n          isFounder\n          isPinnedToSubscriptionOverview\n          isPrivate\n          matureAccess\n          modifiedOn\n          name\n          owners {\n            ...OwnerFields\n          }\n          premium\n          publishedOn\n          privacyLevel\n          profileSectionId\n          slug\n          url\n        }\n      }\n    }\n  }\n  \n  fragment OwnerFields on User {\n    displayName\n    id\n    isFollowing\n    isProfileOwner\n    location\n    locationUrl\n    url\n    username\n  }",
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

    async def async_startup(self) -> None:
        # Load initial cookies by requesting the primary URL
        await self.request_soup(self.PRIMARY_URL, impersonate=True)
        self.update_cookies({"originalReferrer": "", "ilo0": "true", "ilo1": "true"})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["gallery", gallery_id, gallery_name, "modules", _]:
                return await self.image(scrape_item)
            case ["gallery", gallery_id, gallery_name]:
                return await self.gallery(scrape_item, gallery_id, gallery_name)
            case [user_name]:
                return await self.profile(scrape_item, user_name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, gallery_id: str, gallery_name: str) -> None:
        results = await self.get_album_results(gallery_id)
        title = self.create_title(gallery_name, gallery_id)
        scrape_item.setup_as_album(title)

        soup = await self.request_soup(scrape_item.url)
        modules = soup.select("a.ImageElement-root-kir")
        for module in modules:
            module_link = css.get_attr(module, "href")
            img_link = css.select_one_get_attr_or_none(module, "img.ImageElement-image-SRv", "srcset")
            if not module_link or not img_link:
                continue
            if results and self.check_album_results(self.parse_url(module_link), results):
                continue
            new_scrape_item = scrape_item.create_child(self.parse_url(module_link))
            self.create_task(self.direct_file(new_scrape_item, self.parse_url(img_link)))
            scrape_item.add_children()

        # Add Grid Images those do not have module links
        grid_images = soup.select("picture[data-ut='project-module-picture']")
        for image in grid_images:
            img_link = css.select_one_get_attr_or_none(
                image, "source[data-ut='project-module-source-original']", "srcset"
            )
            if not img_link:
                continue
            if results and self.check_album_results(self.parse_url(img_link), results):
                continue
            new_scrape_item = scrape_item.create_child(self.parse_url(img_link))
            self.create_task(self.direct_file(new_scrape_item))
            scrape_item.add_children()

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        link_str: str = css.select(soup, IMAGE_SELECTOR, "src")
        link = self.parse_url(link_str).with_query(None)
        await self.direct_file(scrape_item, link)

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

        self.update_cookies({"bcp": BCP_VALUE})

        while hasNextPage:
            response = await self.request_json(
                GRAPHQL_URL,
                method="POST",
                data=json.dumps(request_body),
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
