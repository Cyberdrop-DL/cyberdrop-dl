from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from yarl import URL

from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


def is_valid_url(scrape_item: ScrapeItem) -> bool:
    if not scrape_item.url:
        return False
    if not isinstance(scrape_item.url, URL):
        try:
            scrape_item.url = AbsoluteHttpURL(scrape_item.url)
        except AttributeError:
            return False
    try:
        if not scrape_item.url.host:
            return False
    except AttributeError:
        return False

    return True


def is_outside_date_range(scrape_item: ScrapeItem, before: datetime.date | None, after: datetime.date | None) -> bool:
    skip = False
    item_date = scrape_item.completed_at or scrape_item.created_at
    if not item_date:
        return False
    date = datetime.datetime.fromtimestamp(item_date).date()
    if (after and date < after) or (before and date > before):
        skip = True

    return skip


def is_in_domain_list(scrape_item: ScrapeItem, domain_list: Sequence[str]) -> bool:
    return any(domain in scrape_item.url.host for domain in domain_list)
