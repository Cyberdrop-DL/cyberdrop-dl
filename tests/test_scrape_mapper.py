from __future__ import annotations

import pytest

from cyberdrop_dl import scrape_mapper
from cyberdrop_dl.config import Config
from cyberdrop_dl.crawlers import create_crawlers
from cyberdrop_dl.crawlers._chevereto import CheveretoCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL


@pytest.mark.parametrize(
    "link",
    [
        "https://bunkr.com",
        "https://dropbox.uk",
        "https://forum.allporncomix.com",
        "https://cyberfile.me/abhl",
        "https://forums.plex.tv/",
        "https://forums.socialmediagirls.com/threads/en-fr-tools-to-download-upload-content-websites-softwares-extensions.13930/#post-2070848",
    ],
)
def test_generic_crawlers_that_match_supported_crawlers_should_not_be_created(link: str) -> None:
    crawlers = scrape_mapper.get_crawlers_mapping()
    crawler = next(iter(create_crawlers([link], CheveretoCrawler)))
    with pytest.raises(ValueError) as exc_info:
        scrape_mapper.register_crawler(crawlers, crawler, from_user="raise")
    assert f"Unable to assign {link.split('/', maxsplit=1)[0]}" in str(exc_info.value)


@pytest.mark.parametrize(
    "link",
    [
        "https://forum.otherforum.com",
        "https://cyberfolder.me/abhl",
        "https://meta.discourse.org/",
    ],
)
def test_generic_crawlers_that_do_no_match_supported_crawlers_should_be_created(link: str) -> None:
    existing_crawlers = scrape_mapper.get_crawlers_mapping()
    crawlers_before = set(existing_crawlers.values())
    crawler = next(iter(create_crawlers([link], CheveretoCrawler)))
    scrape_mapper.register_crawler(existing_crawlers, crawler, from_user="raise")
    new_crawlers = set(existing_crawlers.values()) - crawlers_before
    assert len(new_crawlers) == 1
    created_crawler = next(iter(new_crawlers))
    assert issubclass(created_crawler, CheveretoCrawler)


def test_skip_by_config() -> None:
    url = AbsoluteHttpURL("https://example.com")
    config = Config()
    assert scrape_mapper._skip_by_config(url, config) is False
    config.filters.skip_hosts = {url.host}
    assert scrape_mapper._skip_by_config(url, config) is True
    config.filters.skip_hosts.clear()
    config.filters.only_hosts = {"google.com"}
    assert scrape_mapper._skip_by_config(url, config) is True
