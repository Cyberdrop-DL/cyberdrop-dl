# ruff: noqa: S105
from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any
from unittest import mock

import pytest
from multidict import CIMultiDict, CIMultiDictProxy

from cyberdrop_dl.crawlers.deviantart.api import DeviantArtAPI
from cyberdrop_dl.crawlers.deviantart.crawler import DeviantArtCrawler
from cyberdrop_dl.exceptions import DownloadError, LoginError, ScrapeError
from cyberdrop_dl.logs import LOG_HTTP_TRAFFIC
from cyberdrop_dl.scrape_mapper import ScrapeMapper
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem, ScrapeItem

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from cyberdrop_dl.manager import Manager


class FakeResponse:
    def __init__(
        self,
        url: AbsoluteHttpURL | str,
        *,
        status: int = 200,
        json_data: Any = None,
        headers: dict[str, str] | None = None,
        content_type: str = "application/json",
    ) -> None:
        self.url: AbsoluteHttpURL = AbsoluteHttpURL(url)
        self.status: int = status
        self._json_data: Any = json_data
        raw_headers = {"content-type": content_type} | (headers or {})
        self.headers: CIMultiDictProxy[str] = CIMultiDictProxy(CIMultiDict(raw_headers))
        self.content_type: str = content_type
        self.location: AbsoluteHttpURL | None = None
        self.id: str = "fake-id"
        self.has_content_not_logged: bool = False

    async def json(self) -> Any:
        return self._json_data

    async def text(self) -> str:
        if isinstance(self._json_data, str):
            return self._json_data
        return json.dumps(self._json_data)


def _make_deviation_payload(
    deviation_id: str = "11111111-2222-3333-4444-555555555555",
    *,
    title: str = "Test Art",
    content_src: str = "https://images-wixmp-abc.wixmp.com/f/preview/test_image.png?token=sig123",
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "deviationid": deviation_id,
        "url": extra.pop("url", f"https://www.deviantart.com/artist/art/Test-Art-{deviation_id}"),
        "title": title,
        "published_time": "1700000000",
        "is_deleted": False,
        "is_mature": extra.pop("is_mature", False),
        "is_downloadable": extra.pop("is_downloadable", False),
        "author": {"userid": "uuid-author", "username": "artist"},
        "thumbs": [{"src": "https://images-wixmp-abc.wixmp.com/f/thumb/thumb.jpg", "width": 150, "height": 150}],
    }
    if content_src:
        payload["content"] = {"src": content_src, "width": 1000, "height": 1000}
    payload.update(extra)
    return payload


def _make_crawler(manager: Manager) -> tuple[ScrapeMapper, DeviantArtCrawler]:
    mapper = ScrapeMapper(manager)
    manager.scrape_mapper = mapper
    crawler = mapper._factory(DeviantArtCrawler)
    return mapper, crawler


def _make_scrape_item(url: str, manager: Manager) -> ScrapeItem:
    item = ScrapeItem.from_url(url)
    item.download_folder = manager.config.download_folder
    return item


def _patch_raw_request(
    crawler: DeviantArtCrawler,
    handler: Callable[[AbsoluteHttpURL, str, dict[str, Any]], FakeResponse],
) -> list[tuple[AbsoluteHttpURL, str, dict[str, Any], bool]]:
    recorded: list[tuple[AbsoluteHttpURL, str, dict[str, Any], bool]] = []

    @contextlib.asynccontextmanager
    async def fake_raw_request(url: AbsoluteHttpURL, method: str = "GET", **kwargs: Any) -> AsyncIterator[FakeResponse]:
        recorded.append((url, method, dict(kwargs), LOG_HTTP_TRAFFIC.get()))
        yield handler(url, method, kwargs)

    crawler.client.raw_request = fake_raw_request  # type: ignore[method-assign]
    return recorded


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("www.deviantart.com", True),
        ("deviantart.com", True),
        ("fav.me", True),
        ("evil-deviantart.com", False),
        ("deviantart.com.evil.com", False),
    ],
)
def test_strict_host_matching(host: str, *, expected: bool) -> None:
    assert DeviantArtCrawler.check_host_match(host) is expected


@pytest.mark.parametrize(
    ("url", "expected_method", "expected_args"),
    [
        (
            "https://www.deviantart.com/artist/art/cool-work-11111111-2222-3333-4444-555555555555",
            "deviation",
            ("artist", "cool-work-11111111-2222-3333-4444-555555555555"),
        ),
        ("https://www.deviantart.com/artist", "gallery", ("artist",)),
        ("https://www.deviantart.com/artist/gallery", "gallery", ("artist",)),
        ("https://www.deviantart.com/artist/gallery/all", "gallery", ("artist",)),
        ("https://www.deviantart.com/artist/gallery/scraps", "scraps", ("artist",)),
        (
            "https://www.deviantart.com/artist/gallery/99999/my-folder",
            "gallery_folder",
            ("artist", "99999", "my-folder"),
        ),
        ("https://www.deviantart.com/artist/favourites", "favourites", ("artist",)),
        ("https://www.deviantart.com/artist/favourites/all", "favourites", ("artist",)),
        (
            "https://www.deviantart.com/artist/favourites/88888/fav-folder",
            "collection_folder",
            ("artist", "88888", "fav-folder"),
        ),
        ("https://fav.me/d123abc", "fav_me", ()),
    ],
)
async def test_fetch_routing(
    running_manager: Manager,
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    expected_method: str,
    expected_args: tuple[str, ...],
) -> None:
    _, crawler = _make_crawler(running_manager)
    called: list[tuple[str, tuple[Any, ...]]] = []

    async def fake_handler(_item: ScrapeItem, *args: Any) -> None:
        called.append((expected_method, args))

    monkeypatch.setattr(crawler, expected_method, fake_handler)
    item = ScrapeItem.from_url(url)
    await crawler.fetch(item)
    assert called == [(expected_method, expected_args)]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.deviantart.com/watch",
        "https://www.deviantart.com/settings",
        "https://www.deviantart.com/artist/unknown/extra",
        "https://fav.me/",
        "https://fav.me/a/b",
    ],
)
async def test_fetch_rejects_invalid_paths(running_manager: Manager, url: str) -> None:
    _, crawler = _make_crawler(running_manager)
    with pytest.raises(ValueError):
        await crawler.fetch(ScrapeItem.from_url(url))


async def test_fav_me_redirect_resolution(running_manager: Manager, monkeypatch: pytest.MonkeyPatch) -> None:
    _, crawler = _make_crawler(running_manager)
    canonical = AbsoluteHttpURL("https://www.deviantart.com/artist/art/Nice-123456")
    monkeypatch.setattr(crawler, "request_redirect", mock.AsyncMock(return_value=canonical))
    created: list[Any] = []
    monkeypatch.setattr(crawler, "create_task", created.append)

    item = ScrapeItem.from_url("https://fav.me/d123abc")
    await crawler.fav_me(item)

    assert item.url == canonical
    assert len(created) == 1
    created[0].close()


async def test_missing_credentials_raises_login_error(running_manager: Manager) -> None:
    _, crawler = _make_crawler(running_manager)
    with pytest.raises(LoginError):
        await crawler.api.ensure_token()


async def test_client_credentials_oauth_caching(running_manager: Manager) -> None:
    running_manager.config.auth.deviantart.client_id = "cid-123"
    running_manager.config.auth.deviantart.client_secret = "csec-secret"

    _, crawler = _make_crawler(running_manager)
    calls = 0

    def handler(url: AbsoluteHttpURL, method: str, kwargs: dict[str, Any]) -> FakeResponse:
        nonlocal calls
        calls += 1
        assert url == DeviantArtAPI.OAUTH_URL
        assert method == "POST"
        assert kwargs["data"] == {
            "grant_type": "client_credentials",
            "client_id": "cid-123",
            "client_secret": "csec-secret",
        }
        return FakeResponse(url, json_data={"access_token": "app-tok-1", "expires_in": 3600})

    recorded = _patch_raw_request(crawler, handler)

    tok1 = await crawler.api.ensure_token()
    tok2 = await crawler.api.ensure_token()
    assert tok1 == "app-tok-1"
    assert tok2 == "app-tok-1"
    assert calls == 1
    assert recorded[0][3] is False  # LOG_HTTP_TRAFFIC suppressed


async def test_refresh_token_pkce_rotation_and_cache_reset_on_config_change(running_manager: Manager) -> None:
    running_manager.config.auth.deviantart.client_id = "pkce-cid"
    running_manager.config.auth.deviantart.refresh_token = "seed-rt-1"

    _, crawler1 = _make_crawler(running_manager)
    token_requests: list[dict[str, str]] = []

    def handler_first(url: AbsoluteHttpURL, _method: str, kwargs: dict[str, Any]) -> FakeResponse:
        token_requests.append(kwargs["data"])
        return FakeResponse(
            url,
            json_data={
                "access_token": "user-tok-1",
                "refresh_token": "rotated-rt-2",
                "expires_in": 3600,
            },
        )

    _patch_raw_request(crawler1, handler_first)
    tok1 = await crawler1.api.ensure_token()
    assert tok1 == "user-tok-1"
    assert token_requests[0] == {
        "grant_type": "refresh_token",
        "client_id": "pkce-cid",
        "refresh_token": "seed-rt-1",
    }
    assert "client_secret" not in token_requests[0]

    # Simulate expiry near threshold (< 60s) on a fresh API instance sharing manager.cache
    cached = crawler1.cache.get("oauth")
    assert cached is not None
    assert cached["refresh_token"] == "rotated-rt-2"
    cached["expires_at"] = time.time() + 30
    crawler1.cache.save("oauth", cached, ttl=None)

    crawler2_api = DeviantArtAPI.from_crawler(crawler1)

    def handler_second(url: AbsoluteHttpURL, _method: str, kwargs: dict[str, Any]) -> FakeResponse:
        token_requests.append(kwargs["data"])
        return FakeResponse(
            url,
            json_data={
                "access_token": "user-tok-2",
                "refresh_token": "rotated-rt-3",
                "expires_in": 3600,
            },
        )

    @contextlib.asynccontextmanager
    async def fake_raw_2(url: AbsoluteHttpURL, method: str = "GET", **kwargs: Any) -> AsyncIterator[FakeResponse]:
        yield handler_second(url, method, kwargs)

    crawler2_api.client.raw_request = fake_raw_2  # type: ignore[method-assign]
    tok2 = await crawler2_api.ensure_token()
    assert tok2 == "user-tok-2"
    assert token_requests[1]["refresh_token"] == "rotated-rt-2"

    # Changing config refresh_token invalidates old cache cleanly
    running_manager.config.auth.deviantart.refresh_token = "new-seed-rt"
    tok3 = await crawler2_api.ensure_token()
    assert tok3 == "user-tok-2"
    assert token_requests[2]["refresh_token"] == "new-seed-rt"


async def test_401_triggers_single_refresh_retry_preserving_rotated_refresh_token(running_manager: Manager) -> None:
    running_manager.config.auth.deviantart.client_id = "cid"
    running_manager.config.auth.deviantart.client_secret = "csec"
    running_manager.config.auth.deviantart.refresh_token = "seed-rt"

    _, crawler = _make_crawler(running_manager)
    crawler.cache.save(
        "oauth",
        {
            "access_token": "stale-tok",
            "refresh_token": "rotated-rt-99",
            "expires_at": time.time() + 3600,
            "seed_hash": hashlib.sha256(b"cid:csec:seed-rt").hexdigest(),
        },
        ttl=None,
    )

    api_calls: list[str] = []
    refresh_payloads: list[dict[str, str]] = []

    def handler(url: AbsoluteHttpURL, _method: str, kwargs: dict[str, Any]) -> FakeResponse:
        if url == DeviantArtAPI.OAUTH_URL:
            refresh_payloads.append(kwargs["data"])
            return FakeResponse(
                url,
                json_data={
                    "access_token": "fresh-tok",
                    "refresh_token": "rotated-rt-100",
                    "expires_in": 3600,
                },
            )

        auth_header = kwargs["headers"]["Authorization"]
        api_calls.append(auth_header)
        if auth_header == "Bearer stale-tok":
            return FakeResponse(url, status=401, json_data={"error": "invalid_token"})
        return FakeResponse(url, json_data=_make_deviation_payload())

    _patch_raw_request(crawler, handler)
    deviation = await crawler.api.deviation("11111111-2222-3333-4444-555555555555")
    assert deviation.title == "Test Art"
    assert api_calls == ["Bearer stale-tok", "Bearer fresh-tok"]
    assert len(refresh_payloads) == 1
    assert refresh_payloads[0]["refresh_token"] == "rotated-rt-99"


async def test_429_retries_with_retry_after_and_exhausts_cleanly(
    running_manager: Manager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running_manager.config.auth.deviantart.client_id = "cid"
    running_manager.config.auth.deviantart.client_secret = "csec"

    _, crawler = _make_crawler(running_manager)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("cyberdrop_dl.crawlers.deviantart.api.asyncio.sleep", fake_sleep)

    attempts = 0

    def handler(url: AbsoluteHttpURL, _method: str, _kwargs: dict[str, Any]) -> FakeResponse:
        nonlocal attempts
        if url == DeviantArtAPI.OAUTH_URL:
            return FakeResponse(url, json_data={"access_token": "tok", "expires_in": 3600})
        attempts += 1
        if attempts <= 2:
            return FakeResponse(url, status=429, headers={"Retry-After": "3"}, json_data={"error": "rate_limited"})
        return FakeResponse(url, json_data=_make_deviation_payload())

    _patch_raw_request(crawler, handler)
    deviation = await crawler.api.deviation("11111111-2222-3333-4444-555555555555")
    assert deviation.deviationid == "11111111-2222-3333-4444-555555555555"
    assert sleeps == [3.0, 3.0]

    # Exhaust all 429 retries
    sleeps.clear()

    def always_429(url: AbsoluteHttpURL, _method: str, _kwargs: dict[str, Any]) -> FakeResponse:
        if url == DeviantArtAPI.OAUTH_URL:
            return FakeResponse(url, json_data={"access_token": "tok", "expires_in": 3600})
        return FakeResponse(url, status=429, headers={"Retry-After": "1"}, content_type="text/plain")

    _patch_raw_request(crawler, always_429)
    with pytest.raises(DownloadError) as exc_info:
        await crawler.api.deviation("11111111-2222-3333-4444-555555555555")
    assert exc_info.value.status == 429
    assert sleeps == [1.0, 1.0, 1.0]


async def test_security_blocks_non_deviantart_hosts_and_leaks(
    running_manager: Manager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    running_manager.config.auth.deviantart.client_id = "cid"
    running_manager.config.auth.deviantart.client_secret = "super-secret-value"
    running_manager.config.auth.deviantart.refresh_token = "super-refresh-token"

    _, crawler = _make_crawler(running_manager)
    recorded = _patch_raw_request(
        crawler,
        lambda url, _m, _k: FakeResponse(url, json_data={"access_token": "secret-bearer", "expires_in": 3600}),
    )

    with pytest.raises(ScrapeError, match="non-official host"):
        await crawler.api._api_json(AbsoluteHttpURL("https://evil.example.com/api"))
    with pytest.raises(ScrapeError, match="non-official host"):
        await crawler.api._api_json(AbsoluteHttpURL("https://images-wixmp-123.wixmp.com/f/img.jpg"))
    assert recorded == []

    # Response redirecting off-domain must also fail
    def redirect_off_domain(url: AbsoluteHttpURL, _m: str, _k: dict[str, Any]) -> FakeResponse:
        if url == DeviantArtAPI.OAUTH_URL:
            return FakeResponse(url, json_data={"access_token": "secret-bearer", "expires_in": 3600})
        return FakeResponse("https://attacker.example.org/steal", json_data={})

    _patch_raw_request(crawler, redirect_off_domain)
    with caplog.at_level(logging.DEBUG), pytest.raises(ScrapeError, match="non-official host"):
        await crawler.api.deviation("11111111-2222-3333-4444-555555555555")

    assert LOG_HTTP_TRAFFIC.get() is True  # Restored after context exits
    assert "super-secret-value" not in caplog.text
    assert "super-refresh-token" not in caplog.text
    assert "secret-bearer" not in caplog.text


async def test_numeric_deviation_html_lookup_and_literature_and_folder_resolution(
    running_manager: Manager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running_manager.config.auth.deviantart.client_id = "cid"
    running_manager.config.auth.deviantart.client_secret = "csec"

    mapper, crawler = _make_crawler(running_manager)
    monkeypatch.setattr(type(mapper.logs), "write_jsonl", mock.AsyncMock())
    monkeypatch.setattr(
        crawler,
        "request_text",
        mock.AsyncMock(
            return_value='<meta property="da:appurl" content="DeviantArt://deviation/11111111-2222-3333-4444-555555555559">'
        ),
    )
    metadata_writes: list[tuple[str, Any]] = []

    async def capture_metadata(_item: ScrapeItem, name: str, metadata: object) -> None:
        metadata_writes.append((name, metadata))

    monkeypatch.setattr(crawler, "write_metadata", capture_metadata)

    lit_uuid = "11111111-2222-3333-4444-555555555559"
    folder_uuid = "ffffffff-2222-3333-4444-555555555559"
    handled_items: list[MediaItem] = []

    async def capture_media(item: MediaItem, _streams: Any = None) -> None:
        handled_items.append(item)

    monkeypatch.setattr(crawler, "handle_media_item", capture_media)

    def handler(url: AbsoluteHttpURL, _m: str, _k: dict[str, Any]) -> FakeResponse:
        if url == DeviantArtAPI.OAUTH_URL:
            return FakeResponse(url, json_data={"access_token": "tok", "expires_in": 3600})
        if url.path.endswith(f"/deviation/{lit_uuid}"):
            return FakeResponse(
                url,
                json_data=_make_deviation_payload(lit_uuid, title="Story", content_src="", excerpt="Once upon a time"),
            )
        if url.path.endswith("/deviation/content"):
            return FakeResponse(url, json_data={"html": "<p>Full story</p>"})
        if url.path.endswith("/collections/folders"):
            return FakeResponse(
                url,
                json_data={"has_more": False, "results": [{"folderid": folder_uuid, "name": "Cool Favs", "size": 1}]},
            )
        if url.path.endswith(f"/collections/{folder_uuid}"):
            return FakeResponse(
                url,
                json_data={
                    "has_more": False,
                    "name": "Cool Favs",
                    "results": [
                        _make_deviation_payload(
                            "11111111-2222-3333-4444-555555555558",
                            content_src="https://images-wixmp-abc.wixmp.com/f/fav.jpg",
                        )
                    ],
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")

    _patch_raw_request(crawler, handler)

    await crawler.deviation(
        _make_scrape_item("https://www.deviantart.com/artist/art/Story-12345", running_manager), "artist", "Story-12345"
    )
    assert len(metadata_writes) == 1
    assert metadata_writes[0][0] == f"deviation_{lit_uuid}"

    await crawler.collection_folder(
        _make_scrape_item("https://www.deviantart.com/artist/favourites/77777/cool-favs", running_manager),
        "artist",
        "77777",
        "cool-favs",
    )
    assert len(handled_items) == 1
    assert str(handled_items[0].url) == "https://images-wixmp-abc.wixmp.com/f/fav.jpg"


async def test_media_selection_original_fallback_and_no_header_leak(
    running_manager: Manager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running_manager.config.auth.deviantart.client_id = "cid"
    running_manager.config.auth.deviantart.client_secret = "csec"

    mapper, crawler = _make_crawler(running_manager)
    monkeypatch.setattr(type(mapper.logs), "write_jsonl", mock.AsyncMock())
    handled_items: list[MediaItem] = []

    async def capture_media(item: MediaItem, _streams: Any = None) -> None:
        handled_items.append(item)

    monkeypatch.setattr(crawler, "handle_media_item", capture_media)

    dev_id_1 = "11111111-2222-3333-4444-555555555551"
    dev_id_2 = "11111111-2222-3333-4444-555555555552"
    dev_id_3 = "11111111-2222-3333-4444-555555555553"

    def handler(url: AbsoluteHttpURL, _m: str, _k: dict[str, Any]) -> FakeResponse:
        if url == DeviantArtAPI.OAUTH_URL:
            return FakeResponse(url, json_data={"access_token": "bearer-xyz", "expires_in": 3600})
        if f"deviation/download/{dev_id_1}" in url.path:
            return FakeResponse(
                url,
                json_data={
                    "src": "https://images-wixmp-abc.wixmp.com/f/orig/full_art.png?token=abc",
                    "filename": "full_art_original.png",
                },
            )
        if f"deviation/download/{dev_id_2}" in url.path:
            return FakeResponse(url, status=403, json_data={"error": "download_disabled"})
        if f"deviation/{dev_id_1}" in url.path:
            return FakeResponse(url, json_data=_make_deviation_payload(dev_id_1, is_downloadable=True))
        if f"deviation/{dev_id_2}" in url.path:
            return FakeResponse(
                url,
                json_data=_make_deviation_payload(
                    dev_id_2,
                    is_downloadable=True,
                    content_src="https://images-wixmp-abc.wixmp.com/f/preview/fallback.jpg",
                ),
            )
        if f"deviation/{dev_id_3}" in url.path:
            return FakeResponse(
                url,
                json_data=_make_deviation_payload(
                    dev_id_3,
                    content_src="",
                    videos=[
                        {"src": "https://wixmp.com/v/360.mp4", "quality": "360p", "filesize": 100},
                        {"src": "https://wixmp.com/v/1080.mp4", "quality": "1080p", "filesize": 500},
                    ],
                ),
            )
        raise AssertionError(f"Unexpected URL: {url}")

    _patch_raw_request(crawler, handler)

    # 1. Download original succeeds
    await crawler.deviation(
        _make_scrape_item(f"https://www.deviantart.com/artist/art/a-{dev_id_1}", running_manager), "artist", dev_id_1
    )
    # 2. Download original fails -> graceful fallback to content.src
    await crawler.deviation(
        _make_scrape_item(f"https://www.deviantart.com/artist/art/b-{dev_id_2}", running_manager), "artist", dev_id_2
    )
    # 3. Video deviation -> picks highest quality video
    await crawler.deviation(
        _make_scrape_item(f"https://www.deviantart.com/artist/art/c-{dev_id_3}", running_manager), "artist", dev_id_3
    )

    assert len(handled_items) == 3
    assert str(handled_items[0].url) == "https://images-wixmp-abc.wixmp.com/f/orig/full_art.png?token=abc"
    assert handled_items[0].original_filename == "full_art_original.png"
    assert str(handled_items[1].url) == "https://images-wixmp-abc.wixmp.com/f/preview/fallback.jpg"
    assert str(handled_items[2].url) == "https://wixmp.com/v/1080.mp4"

    for item in handled_items:
        assert "Authorization" not in item.headers
        assert "bearer-xyz" not in json.dumps(item.serialize(), default=str)


async def test_gallery_scraps_and_mature_filtering(
    running_manager: Manager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running_manager.config.auth.deviantart.client_id = "cid"
    running_manager.config.auth.deviantart.client_secret = "csec"
    running_manager.config.crawlers.deviantart.include_mature = False
    running_manager.config.crawlers.deviantart.include_scraps = True
    running_manager.config.crawlers.deviantart.download_originals = False

    mapper, crawler = _make_crawler(running_manager)
    monkeypatch.setattr(type(mapper.logs), "write_jsonl", mock.AsyncMock())
    handled_items: list[MediaItem] = []

    async def capture_media(item: MediaItem, _streams: Any = None) -> None:
        handled_items.append(item)

    monkeypatch.setattr(crawler, "handle_media_item", capture_media)

    shared_id = "11111111-2222-3333-4444-000000000001"
    mature_id = "11111111-2222-3333-4444-000000000002"
    scrap_id = "11111111-2222-3333-4444-000000000003"
    scraps_folder_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def handler(url: AbsoluteHttpURL, _m: str, _k: dict[str, Any]) -> FakeResponse:
        if url == DeviantArtAPI.OAUTH_URL:
            return FakeResponse(url, json_data={"access_token": "tok", "expires_in": 3600})
        if url.path.endswith("/gallery/all"):
            assert url.query["mature_content"] == "false"
            return FakeResponse(
                url,
                json_data={
                    "has_more": False,
                    "results": [
                        _make_deviation_payload(
                            shared_id,
                            title="Normal",
                            content_src="https://images-wixmp-abc.wixmp.com/f/normal.png",
                        ),
                        _make_deviation_payload(
                            mature_id,
                            title="Mature",
                            is_mature=True,
                            content_src="https://images-wixmp-abc.wixmp.com/f/mature.png",
                        ),
                    ],
                },
            )
        if url.path.endswith("/gallery/folders"):
            return FakeResponse(
                url,
                json_data={
                    "has_more": False,
                    "results": [{"folderid": scraps_folder_id, "name": "Scraps", "size": 2}],
                },
            )
        if url.path.endswith(f"/gallery/{scraps_folder_id}"):
            return FakeResponse(
                url,
                json_data={
                    "has_more": False,
                    "results": [
                        _make_deviation_payload(
                            shared_id,
                            title="Duplicate",
                            content_src="https://images-wixmp-abc.wixmp.com/f/normal.png",
                        ),
                        _make_deviation_payload(
                            scrap_id,
                            title="Scrap Sketch",
                            content_src="https://images-wixmp-abc.wixmp.com/f/scrap.png",
                        ),
                    ],
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")

    _patch_raw_request(crawler, handler)

    item = _make_scrape_item("https://www.deviantart.com/artist", running_manager)
    await crawler.gallery(item, "artist")

    assert len(handled_items) == 2
    urls = {str(m.url) for m in handled_items}
    assert urls == {
        "https://images-wixmp-abc.wixmp.com/f/normal.png",
        "https://images-wixmp-abc.wixmp.com/f/scrap.png",
    }
    assert crawler.tui.files.stats.skipped == 1
