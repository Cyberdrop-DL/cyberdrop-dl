from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL

from .xenforo import XenforoCrawler

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers._forum import ThreadProtocol
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem

# SimpCity-specific logged-in indicator, supplementing the generic XenForo
# markers already checked in the base class.
_EXTRA_LOGIN_MARKERS = ('class="p-navgroup-link--loggedin"',)


class SimpCityCrawler(XenforoCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://simpcity.cr")
    DOMAIN: ClassVar[str] = "simpcity"
    FOLDER_DOMAIN: ClassVar[str] = "SimpCity"
    LOGIN_USER_COOKIE_NAME = "ogaddgmetaprof_user"
    login_required = False
    IGNORE_EMBEDED_IMAGES_SRC = False
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("simpcity.su",)
    _RATE_LIMIT = 1, 20

    @classmethod
    def parse_thread(cls, url: AbsoluteHttpURL, thread_name_and_id: str) -> ThreadProtocol:
        """Return a Thread with its URL normalised to the current primary domain.

        SimpCity migrated from simpcity.su to simpcity.cr.  Without this
        normalisation the scraped-threads deduplication set treats the same
        thread reached via the old and new domains as two distinct threads,
        causing it to be scraped twice.
        """
        thread = super().parse_thread(url, thread_name_and_id)
        if thread.url.host != cls.PRIMARY_URL.host:
            normalised = thread.url.with_host(cls.PRIMARY_URL.host)
            thread = dataclasses.replace(thread, url=normalised)
        return thread

    async def process_thread(self, scrape_item: ScrapeItem, thread: ThreadProtocol) -> None:
        """Set a stable album_id before processing the thread.

        Uses ``str(thread.id)`` as the album_id so the download history
        database has a domain-independent key for every thread.  Combined with
        ``parse_thread``'s URL canonicalization, a thread accessed via either
        ``simpcity.su`` or ``simpcity.cr`` maps to the same album_id,
        enabling cross-run deduplication without modifying base-class logic.
        """
        scrape_item.album_id = str(thread.id)
        await super().process_thread(scrape_item, thread)

    async def check_login_with_request(self, login_url: AbsoluteHttpURL) -> tuple[str, bool]:
        """Extend the generic XenForo login check with a SimpCity-specific marker."""
        text, logged_in = await super().check_login_with_request(login_url)
        if not logged_in:
            logged_in = any(marker in text for marker in _EXTRA_LOGIN_MARKERS)
        return text, logged_in
