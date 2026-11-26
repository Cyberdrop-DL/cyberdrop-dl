"""DeviantArt OAuth2 & REST API v1 client."""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import TYPE_CHECKING, Any, ClassVar, Unpack

from aiohttp import hdrs

from cyberdrop_dl import context
from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.deviantart.models import (
    CachedToken,
    Deviation,
    DeviationContent,
    DeviationListPage,
    DownloadResponse,
    FolderPage,
    OAuthTokenResponse,
)
from cyberdrop_dl.exceptions import DownloadError, LoginError, ScrapeError
from cyberdrop_dl.logs import LOG_HTTP_TRAFFIC
from cyberdrop_dl.network.http import HTTPConfig, check_http_status
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import dates
from cyberdrop_dl.utils.urls import is_within_domain

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.config.auth import DeviantArtAuth
    from cyberdrop_dl.network import HttpMethod
    from cyberdrop_dl.network.request import RequestParams
    from cyberdrop_dl.network.response import AbstractResponse


_MAX_RETRY_AFTER_SECONDS = 60.0
_DEFAULT_BACKOFF_SECONDS = 2.0


class _UnauthorizedError(Exception):
    """Internal signal that an API request returned HTTP 401."""


def _json_check(resp_json: Any, resp: AbstractResponse[Any], /) -> None:
    if type(resp_json) is not dict:
        return

    if error := resp_json.get("error"):
        desc = resp_json.get("error_description") or ""
        msg = f"{error}: {desc}" if desc else str(error)
        raise ScrapeError(resp.status, msg)


def _parse_retry_after(header_value: str | None, attempt: int) -> float:
    fallback = min(_DEFAULT_BACKOFF_SECONDS * (2**attempt), _MAX_RETRY_AFTER_SECONDS)
    if not header_value:
        return fallback

    try:
        seconds = float(header_value)
    except ValueError:
        try:
            target = dates.parse_http(header_value)
        except (TypeError, ValueError):
            return fallback
        seconds = (target - dates.now(utc=True)).total_seconds()

    return min(max(seconds, 0.0), _MAX_RETRY_AFTER_SECONDS)


def _seed_hash(auth: DeviantArtAuth) -> str:
    seed = f"{auth.client_id.strip()}:{auth.client_secret.strip()}:{auth.refresh_token.strip()}"
    return hashlib.sha256(seed.encode()).hexdigest()


def _is_expiring(entry: CachedToken, skew_seconds: float) -> bool:
    return time.time() >= float(entry["expires_at"]) - skew_seconds


@HTTPConfig(rate_limit=(2, 1), json_check=_json_check)
class DeviantArtAPI(API):
    OAUTH_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.deviantart.com/oauth2/token")
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.deviantart.com/api/v1/oauth2")
    _OFFICIAL_DOMAINS: ClassVar[tuple[str, ...]] = ("deviantart.com",)
    _CACHE_KEY: ClassVar[str] = "oauth"
    _EXPIRY_SKEW_SECONDS: ClassVar[int] = 60
    _MAX_429_RETRIES: ClassVar[int] = 3
    _PAGE_LIMIT: ClassVar[int] = 24
    _FOLDER_LIMIT: ClassVar[int] = 50

    def __post_init__(self) -> None:
        self._auth_lock: asyncio.Lock = asyncio.Lock()
        self._token: CachedToken | None = None

    @property
    def mature_param(self) -> str:
        return "true" if self.config.crawlers.deviantart.include_mature else "false"

    @classmethod
    def assert_official_domain(cls, url: AbsoluteHttpURL) -> None:
        if not any(is_within_domain(domain, url.host) for domain in cls._OFFICIAL_DOMAINS):
            raise ScrapeError(403, f"Refusing to send DeviantArt credentials to non-official host: {url.host}")

    def _load_cached_token(self, seed_hash: str) -> CachedToken | None:
        entry = self._token or self.cache.get(self._CACHE_KEY)
        if not isinstance(entry, dict) or entry.get("seed_hash") != seed_hash:
            if self._token is not None or self.cache.get(self._CACHE_KEY) is not None:
                self._clear_cached_token()
            return None

        access_token = entry.get("access_token")
        refresh_token = entry.get("refresh_token")
        expires_at = entry.get("expires_at")
        if not (
            isinstance(access_token, str) and isinstance(refresh_token, str) and isinstance(expires_at, (int, float))
        ):
            self._clear_cached_token()
            return None

        cached: CachedToken = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": float(expires_at),
            "seed_hash": seed_hash,
        }
        self._token = cached
        return cached

    def _save_token(
        self,
        token_resp: OAuthTokenResponse,
        seed_hash: str,
        *,
        fallback_refresh_token: str = "",
    ) -> CachedToken:
        entry: CachedToken = {
            "access_token": token_resp.access_token,
            "refresh_token": token_resp.refresh_token or fallback_refresh_token,
            "expires_at": time.time() + token_resp.expires_in,
            "seed_hash": seed_hash,
        }
        self._token = entry
        self.cache.save(self._CACHE_KEY, entry, ttl=None)
        return entry

    def _invalidate_access_token(self, *, failed_token: str) -> None:
        if self._token and self._token["access_token"] == failed_token:
            updated: CachedToken = {
                "access_token": "",
                "refresh_token": self._token["refresh_token"],
                "expires_at": 0.0,
                "seed_hash": self._token["seed_hash"],
            }
            self._token = updated
            self.cache.save(self._CACHE_KEY, updated, ttl=None)

    def _clear_cached_token(self) -> None:
        self._token = None
        self.cache.discard(self._CACHE_KEY)

    async def ensure_token(self, *, failed_token: str | None = None) -> str:
        auth = self.config.auth.deviantart
        client_id = auth.client_id.strip()
        client_secret = auth.client_secret.strip()
        config_refresh_token = auth.refresh_token.strip()

        if not client_id or not (config_refresh_token or client_secret):
            raise LoginError(
                "DeviantArt authentication requires auth.deviantart.client_id with either "
                "client_secret or refresh_token in config.yaml"
            )

        seed_hash = _seed_hash(auth)
        if failed_token is None:
            cached = self._load_cached_token(seed_hash)
            if cached and cached["access_token"] and not _is_expiring(cached, self._EXPIRY_SKEW_SECONDS):
                return cached["access_token"]

        async with self._auth_lock:
            cached = self._load_cached_token(seed_hash)
            if (
                cached
                and cached["access_token"]
                and (failed_token is None or cached["access_token"] != failed_token)
                and not _is_expiring(cached, self._EXPIRY_SKEW_SECONDS)
            ):
                return cached["access_token"]

            active_refresh_token = (cached["refresh_token"] if cached else "") or config_refresh_token
            if active_refresh_token:
                payload: dict[str, str] = {
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": active_refresh_token,
                }
                if client_secret:
                    payload["client_secret"] = client_secret

                try:
                    token_resp = await self._post_token(payload)
                except LoginError:
                    self._clear_cached_token()
                    raise

                saved = self._save_token(
                    token_resp,
                    seed_hash,
                    fallback_refresh_token=active_refresh_token,
                )
                return saved["access_token"]

            payload = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
            token_resp = await self._post_token(payload)
            saved = self._save_token(token_resp, seed_hash)
            return saved["access_token"]

    async def _post_token(self, payload: dict[str, str]) -> OAuthTokenResponse:
        self.assert_official_domain(self.OAUTH_URL)
        with context.enter(LOG_HTTP_TRAFFIC, False):
            try:
                data = await self._request_json_with_retry(self.OAUTH_URL, method="POST", data=payload)
            except (DownloadError, ScrapeError) as e:
                raise LoginError(f"DeviantArt OAuth authentication failed: {e}") from e

        return OAuthTokenResponse.model_validate(data)

    async def _api_json(
        self,
        url: AbsoluteHttpURL,
        *,
        method: HttpMethod = "GET",
        **kwargs: Unpack[RequestParams],
    ) -> Any:
        self.assert_official_domain(url)
        failed_token: str | None = None
        with context.enter(LOG_HTTP_TRAFFIC, False):
            for retry in (True, False):
                token = await self.ensure_token(failed_token=failed_token)
                headers = dict(kwargs.get("headers") or {})
                headers[hdrs.AUTHORIZATION] = f"Bearer {token}"
                req_kwargs: RequestParams = {**kwargs, "headers": headers}
                try:
                    return await self._request_json_with_retry(url, method=method, **req_kwargs)
                except _UnauthorizedError:
                    if not retry:
                        raise ScrapeError(401, "DeviantArt API rejected access token after refresh") from None
                    self._invalidate_access_token(failed_token=token)
                    failed_token = token

        raise RuntimeError

    async def _request_json_with_retry(
        self,
        url: AbsoluteHttpURL,
        *,
        method: HttpMethod = "GET",
        **kwargs: Unpack[RequestParams],
    ) -> Any:
        base_headers = self.__http_ctx__.headers | (kwargs.get("headers") or {})
        has_auth = hdrs.AUTHORIZATION in base_headers
        if has_auth:
            self.assert_official_domain(url)

        req_kwargs: RequestParams = {**kwargs, "headers": base_headers}
        req_kwargs.setdefault("impersonate", self.__http_ctx__.impersonate)

        for attempt in range(self._MAX_429_RETRIES + 1):
            wait: float | None = None
            async with self.rate_limit_ctx(), self.client.raw_request(url, method, **req_kwargs) as resp:
                if has_auth:
                    self.assert_official_domain(resp.url)

                if resp.status == 429 and attempt < self._MAX_429_RETRIES:
                    wait = _parse_retry_after(resp.headers.get(hdrs.RETRY_AFTER), attempt)
                elif resp.status == 401 and has_auth and url != self.OAUTH_URL:
                    raise _UnauthorizedError
                else:
                    await check_http_status(resp)
                    return await resp.json()

            if wait is not None:
                self.log.warning(
                    "Rate limited (429) by DeviantArt API, retrying in %.1fs (attempt %s/%s)",
                    wait,
                    attempt + 1,
                    self._MAX_429_RETRIES,
                )
                await asyncio.sleep(wait)

        raise RuntimeError

    async def deviation(self, deviation_id: str) -> Deviation:
        url = (self.ENTRYPOINT / "deviation" / deviation_id).with_query(mature_content=self.mature_param)
        return Deviation.model_validate(await self._api_json(url))

    async def download_deviation(self, deviation_id: str) -> DownloadResponse:
        url = (self.ENTRYPOINT / "deviation/download" / deviation_id).with_query(mature_content=self.mature_param)
        return DownloadResponse.model_validate(await self._api_json(url))

    async def deviation_content(self, deviation_id: str) -> DeviationContent:
        url = (self.ENTRYPOINT / "deviation/content").with_query(
            deviationid=deviation_id,
            mature_content=self.mature_param,
        )
        return DeviationContent.model_validate(await self._api_json(url))

    async def _paginate_deviations(
        self,
        url: AbsoluteHttpURL,
        *,
        limit: int | None = None,
    ) -> AsyncGenerator[DeviationListPage]:
        page_limit = limit or self._PAGE_LIMIT
        offset = 0
        while True:
            page_url = url.update_query(offset=offset, limit=page_limit, mature_content=self.mature_param)
            page = DeviationListPage.model_validate(await self._api_json(page_url))
            yield page
            if not page.has_more or page.next_offset is None or page.next_offset <= offset:
                break
            offset = page.next_offset

    async def _paginate_folders(self, url: AbsoluteHttpURL) -> AsyncGenerator[FolderPage]:
        offset = 0
        while True:
            page_url = url.update_query(
                calculate_size="true",
                ext_preload="false",
                offset=offset,
                limit=self._FOLDER_LIMIT,
                mature_content=self.mature_param,
            )
            page = FolderPage.model_validate(await self._api_json(page_url))
            yield page
            if not page.has_more or page.next_offset is None or page.next_offset <= offset:
                break
            offset = page.next_offset

    def gallery_all(self, username: str) -> AsyncGenerator[DeviationListPage]:
        url = (self.ENTRYPOINT / "gallery/all").with_query(username=username)
        return self._paginate_deviations(url)

    def gallery_folders(self, username: str) -> AsyncGenerator[FolderPage]:
        url = (self.ENTRYPOINT / "gallery/folders").with_query(username=username)
        return self._paginate_folders(url)

    def gallery_folder(self, username: str, folder_id: str) -> AsyncGenerator[DeviationListPage]:
        url = (self.ENTRYPOINT / "gallery" / folder_id).with_query(username=username)
        return self._paginate_deviations(url)

    def collections_all(self, username: str) -> AsyncGenerator[DeviationListPage]:
        url = (self.ENTRYPOINT / "collections/all").with_query(username=username)
        return self._paginate_deviations(url)

    def collection_folders(self, username: str) -> AsyncGenerator[FolderPage]:
        url = (self.ENTRYPOINT / "collections/folders").with_query(username=username)
        return self._paginate_folders(url)

    def collection_folder(self, username: str, folder_id: str) -> AsyncGenerator[DeviationListPage]:
        url = (self.ENTRYPOINT / "collections" / folder_id).with_query(username=username)
        return self._paginate_deviations(url)
