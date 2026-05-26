from __future__ import annotations

from pathlib import Path

import aiohttp
import pytest
from bs4 import BeautifulSoup

from cyberdrop_dl.utils import next_js

TEST_HTML = (Path(__file__).parent / "nextjsv13.html").read_text()
TEST_SOUP = BeautifulSoup(TEST_HTML, "html.parser")


@pytest.fixture(name="next_data", scope="module")
async def onepace_flight_data() -> next_js.NextJSFlight:
    async with aiohttp.ClientSession() as session:
        resp = await session.get("https://onepace.net/en/watch")
        soup = BeautifulSoup(await resp.text(), "html.parser")
        return next_js.extract(soup)


def test_extract_raw_pushes() -> None:
    pushes = list(next_js._extract_raw_pushes(TEST_SOUP))
    assert len(pushes) == 26
    for push in pushes:
        chunk_id, _, data = push[1:-1].partition(",")
        assert chunk_id == chunk_id.strip()
        assert data == data.strip()


@pytest.mark.parametrize(
    ("push", "expected_type", "expected_value"),
    [
        ("[0]", next_js._FlightType.BOOTSTRAP, "<INIT>"),
        ('[1,"1:$Sreact.fragment"]', next_js._FlightType.PAYLOAD, "1:$Sreact.fragment"),
    ],
)
def test_decode_push(push: str, expected_type: next_js._FlightType, expected_value: object) -> None:
    push_type, value = next_js._decode_push(push)
    assert push_type is expected_type
    assert value == expected_value


def test_extract_flight_data_remove_undefined() -> None:
    assert "$undefined" in TEST_HTML
    assert "$undefined" not in next_js.extract_flight_data(TEST_SOUP)


def test_parse() -> None:
    flight_data = next_js.extract_flight_data(TEST_SOUP)
    chunks = next_js.parse(flight_data)
    assert len(chunks) == 111
    for value in chunks.values():
        assert value != next_js._Magic.ERROR


def test_next_js_parser(next_data: next_js.NextJSFlight) -> None:
    assert isinstance(next_data, dict)
    assert next_data["1"] == "Sreact.fragment"
    assert len(next_data) > 10


def test_next_js_find(next_data: next_js.NextJSFlight) -> None:
    episode_keys = "slug", "title", "playlistGroups"
    ep = next_js.find(next_data, *episode_keys)
    assert isinstance(ep, dict)
    assert set(episode_keys).issubset(ep.keys())
    all_episodes = list(next_js.ifind(next_data, *episode_keys))
    assert len(all_episodes) > 75
    for ep in all_episodes:
        assert isinstance(ep, dict)
        assert set(episode_keys).issubset(ep.keys())
