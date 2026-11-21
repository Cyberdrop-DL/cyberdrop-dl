from __future__ import annotations

import asyncio
import warnings
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from curl_cffi import CurlSslVersion
    from curl_cffi.requests import AsyncSession, BrowserTypeLiteral
    from curl_cffi.requests.models import Response as CurlResponse

    from cyberdrop_dl.config import Config


DEFAULT_TARGET = "chrome"


def cast_tls(version: Literal["1.2", "1.3"]) -> CurlSslVersion:
    from curl_cffi import CurlSslVersion

    match version:
        case "1.2":
            return CurlSslVersion.TLSv1_2
        case "1.3":
            return CurlSslVersion.TLSv1_3
        case _:
            raise ValueError(version)


def create_session(config: Config) -> AsyncSession[CurlResponse]:
    from curl_cffi import CurlFollow, CurlHttpVersion, CurlOpt, CurlSslVersion
    from curl_cffi.aio import AsyncCurl
    from curl_cffi.requests import AsyncSession
    from curl_cffi.utils import CurlCffiWarning

    loop = asyncio.get_running_loop()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=CurlCffiWarning)
        acurl = AsyncCurl(loop=loop)

    net = config.network

    curl_options: dict[CurlOpt, Any] = {
        CurlOpt.SSLVERSION: cast_tls(net.tls.min_version) | CurlSslVersion.MAX_DEFAULT,
    }

    if not net.tls.verify:
        curl_options.update({CurlOpt.PROXY_SSL_VERIFYPEER: 0, CurlOpt.PROXY_SSL_VERIFYHOST: 0})

    return AsyncSession(
        loop=loop,
        async_curl=acurl,
        impersonate=DEFAULT_TARGET,
        verify=net.tls.verify,
        proxy=str(net.proxy) if net.proxy else None,
        timeout=net.connection_timeout if net.read_timeout is None else (net.connection_timeout, net.read_timeout),
        max_redirects=8,
        allow_redirects=CurlFollow.SAFE,
        http_version=CurlHttpVersion.V2_0,
        curl_options=curl_options,
    )


def cast_impersonation(value: str | bool | None, /) -> BrowserTypeLiteral | None:  # noqa: FBT001
    if not value:
        return None
    if value is True:
        value = DEFAULT_TARGET
    return cast("BrowserTypeLiteral", value)
