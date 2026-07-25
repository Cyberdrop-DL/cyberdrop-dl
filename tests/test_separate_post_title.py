from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cyberdrop_dl.crawlers.crawler import Crawler
from cyberdrop_dl.crawlers.fsiblog import FSIBlogCrawler
from cyberdrop_dl.crawlers.nsfw_xxx import NsfwXXXCrawler
from cyberdrop_dl.crawlers.patreon import PatreonCrawler

if TYPE_CHECKING:
    from cyberdrop_dl.manager import Manager

ISO_DATE = "2024-01-15T10:30:00+00:00"

# Crawlers that pass a `parse_date` / `parse_iso_date` result to `create_separate_post_title`
# and whose default post title format has a strftime spec for it
CRAWLERS_WITH_DATE_IN_POST_TITLE = [PatreonCrawler, FSIBlogCrawler, NsfwXXXCrawler]


def test_parse_date_returns_a_float() -> None:
    assert isinstance(Crawler.parse_iso_date(ISO_DATE), float)
    assert isinstance(Crawler.parse_date("January 2024", "%B %Y"), float)


@pytest.mark.parametrize("crawler_type", CRAWLERS_WITH_DATE_IN_POST_TITLE)
def test_post_title_accepts_the_timestamps_parse_date_returns(manager: Manager, crawler_type: type[Crawler]) -> None:
    crawler = object.__new__(crawler_type)
    crawler.config = manager.config
    assert "2024-01" in crawler.create_separate_post_title("a_title", "1", Crawler.parse_iso_date(ISO_DATE))
