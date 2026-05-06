from collections.abc import AsyncGenerator

import aiohttp
import pytest
from bs4 import BeautifulSoup

from cyberdrop_dl.utils import next_js

pytest.skip("website down", allow_module_level=True)


@pytest.fixture(name="soup", scope="module")
async def onepace_soup() -> AsyncGenerator[BeautifulSoup]:
    async with aiohttp.ClientSession() as session:
        resp = await session.get("https://onepace.net/en/watch")
        yield BeautifulSoup(await resp.text(), "html.parser")


def test_next_js_parser(soup: BeautifulSoup) -> None:
    next_data = next_js.extract(soup)
    assert isinstance(next_data, dict)
    assert next_data["1"] == "Sreact.fragment"
    assert len(next_data) > 10


@pytest.mark.xfail(reason="nextjs parsing is broken")
def test_next_js_find(soup: BeautifulSoup) -> None:
    next_data = next_js.extract(soup)
    episode_keys = "slug", "title", "playGroups"
    ep = next_js.find(next_data, *episode_keys)
    assert isinstance(ep, dict)
    assert set(episode_keys).issubset(ep.keys())
    all_episodes = list(next_js.ifind(next_data, *episode_keys))
    assert len(all_episodes) > 74
    for ep in all_episodes:
        assert isinstance(ep, dict)
        assert set(episode_keys).issubset(ep.keys())
