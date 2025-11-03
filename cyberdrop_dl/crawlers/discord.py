from __future__ import annotations

import asyncio
from dataclasses import dataclass
from json import dumps
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


@dataclass(frozen=True, slots=True)
class DiscordURLData:
    server_id: str = ""
    channel_id: str = ""
    message_id: str = ""

    @property
    def is_dm(self) -> bool:
        return self.server_id == "@me"


PRIMARY_URL = AbsoluteHttpURL("https://discord.com/")


class DiscordCrawler(Crawler):
    SUPPORTED_SITES: ClassVar[dict[str, list]] = {"discord": ["discord", "discordapp", "fixcdn.hyonsu"]}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "discord.com"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Server": "/channels/server_id",
        "Channel": "/channels/server_id/channel_id",
        "Direct Message": "/channels/@me/channel_id",
    }
    API_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://discord.com/api/")

    def __post_init__(self) -> None:
        self.headers = {
            "Authorization": self.manager.config_manager.authentication_data.discord.token,
            "Content-Type": "application/json",
        }

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        """Determines where to send the scrape item based on the url."""
        if "channels" in scrape_item.url.parts:
            parts = scrape_item.url.parts
            if len(parts) > 2 and len(parts) < 5:  # https://discord.com/channels/.../.../...
                # Server/DM or Channel/Group DM
                return await self.scrape(scrape_item)
            elif parts[-1] == "channels":  # https://discord.com/channels
                # Scrape all servers
                return await self.scrape_all_servers(scrape_item)
        elif "attachments" in scrape_item.url.parts:  # https://cdn.discordapp.com/attachments/.../.../...
            return await self.file(scrape_item)
        else:
            raise ValueError

    async def scrape_all_servers(self, scrape_item: ScrapeItem) -> None:
        """Fetches all servers and creates scrape items for each server, then starts them."""
        servers_url = self.API_URL / "v9/users/@me/guilds"
        data = await self.request_json(servers_url, headers=self.headers)
        for server in data:
            server_id = server.get("id")
            server_name = server.get("name")
            if server_id:
                new_url = scrape_item.url / server_id
                new_scrape_item = scrape_item.create_new(new_url, new_title_part=server_name, add_parent=True)
                self.manager.task_group.create_task(self.run(new_scrape_item))

    async def get_request_data(self, scrape_item: ScrapeItem) -> tuple[dict, AbsoluteHttpURL]:
        """Gets the JSON request to use for the desired search."""
        data: DiscordURLData = await self.get_info(scrape_item)

        request_json = {
            "tabs": {
                "media": {
                    "sort_by": "timestamp",
                    "sort_order": "asc",
                    "has": ["image", "video"],
                    "cursor": None,
                    "limit": 25,
                }
            },
            "track_exact_total_hits": True,
        }

        if data.channel_id and not data.is_dm:
            request_json["channel_ids"] = [data.channel_id]
        if not data.is_dm:
            request_json["include_nsfw"] = True

        if data.is_dm:
            # Dicord DM API paths. First case is to scrape a single DM/Group DM. Second case is to scrape all DMs.
            path = f"channels/{data.channel_id}" if data.channel_id else "users/@me"
        else:
            # Discord server API path. Always the same, channel IDs are handled by the JSON.
            path = f"guilds/{data.server_id}"

        full_path = f"v9/{path}/messages/search/tabs"
        request_url = self.API_URL / full_path
        return request_json, request_url

    async def get_media(self, scrape_item: ScrapeItem) -> AsyncGenerator[dict, None]:
        """Uses the Discord mobile app search API to find media."""
        request_json, request_url = await self.get_request_data(scrape_item)

        while True:
            data = await self.request(request_url, data=dumps(request_json), headers=self.headers)
            if "rate limited" in data.get("message", ""):
                wait_time = data.get("retry_after", 0)
                await asyncio.sleep(wait_time * 1.2)
                continue
            media = data.get("tabs", {}).get("media", {})
            messages = media.get("messages", [])

            if messages:
                timestamp = media.get("cursor", {}).get("timestamp")
                yield messages
            else:
                break

            if timestamp:
                request_json["tabs"]["media"]["cursor"] = {"timestamp": timestamp, "type": "timestamp"}

    @error_handling_wrapper
    async def scrape(self, scrape_item: ScrapeItem) -> None:
        """Gets the media from the Discord mobile app search API."""
        async for messages in self.get_media(scrape_item):
            for message in messages:
                await self.process_attachments(message[0], scrape_item)

    async def process_attachments(self, message: dict, scrape_item: ScrapeItem) -> None:
        for attachment in message.get("attachments"):
            url = attachment.get("url")
            filename = attachment.get("filename")
            user_id = message.get("author", {}).get("id")
            username = message.get("author", {}).get("username")
            timestamp = self.parse_date(message.get("timestamp").split("+")[0])

            canonical_url = await self.get_canonical_url(scrape_item.url)
            if await self.check_complete_from_referer(canonical_url):
                continue
            new_scrape_item = scrape_item.create_child(
                url=canonical_url,
                new_title_part=f"{username} ({user_id})",
                possible_datetime=timestamp,
            )

            filename, ext = self.get_filename_and_ext(filename)
            link = self.parse_url(url)
            return await self.handle_file(link, new_scrape_item, filename, ext)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        """Scrapes a file."""
        canonical_url = await self.get_canonical_url(scrape_item.url)
        if await self.check_complete_from_referer(canonical_url):
            return

        new_scrape_item = scrape_item.create_new(url=canonical_url, add_parent=True)

        filename, ext = self.get_filename_and_ext(scrape_item.url.name)
        return await self.handle_file(scrape_item.url, new_scrape_item, filename, ext)

    def get_info(self, scrape_item: ScrapeItem) -> DiscordURLData:
        """Gets the server, channel, and message IDs from the URL."""
        return DiscordURLData(*scrape_item.url.parts[2:5])

    def get_canonical_url(self, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        """Normalizes CDN URLs for consistency."""
        return url.with_host("cdn.discordapp.com")
