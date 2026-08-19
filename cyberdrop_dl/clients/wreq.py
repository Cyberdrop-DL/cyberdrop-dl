from __future__ import annotations

import importlib.util
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any, Literal

IS_INSTALLED = importlib.util.find_spec("wreq") is not None

if TYPE_CHECKING:
    from collections.abc import Generator

    from wreq.cookie import Cookie
    from wreq.emulation import Emulation, Profile
    from wreq.tls import TlsVersion
    from wreq.wreq import Client as WreqClient
    from wreq.wreq import Method
    from wreq.wreq import Response as Response  # noqa: PLC0414

    from cyberdrop_dl.clients import HttpMethod
    from cyberdrop_dl.config import Config
    from cyberdrop_dl.constants import ImpersonateTarget


else:

    class WreqClient: ...

    class Response: ...


def cast_method(method: HttpMethod) -> Method:
    from wreq.wreq import Method

    return getattr(Method, method)


def cast_tls(version: Literal["1.2", "1.3"]) -> TlsVersion:
    from wreq.tls import TlsVersion

    tls = f"TLS_{version.replace('.', '_')}"
    return getattr(TlsVersion, tls)


def cast_impersonate(target: ImpersonateTarget) -> Emulation | Profile:
    from wreq.emulation import Emulation, Platform

    return {
        "chrome": Emulation.Chrome149,
        "edge": Emulation.Edge148,
        "safari": Emulation.Safari26_4,
        "safari_ios": Emulation.SafariIos26_2,
        "chrome_android": Emulation(Emulation.Chrome149, Platform.Android),
        "firefox": Emulation.Firefox151,
    }[target]


def create_client(config: Config) -> WreqClient:
    import datetime

    import wassima
    from wreq import redirect  # pyright: ignore[reportPrivateImportUsage]
    from wreq.dns import DnsOptions
    from wreq.proxy import Proxy
    from wreq.tls import CertStore
    from wreq.wreq import Client as WreqClient

    net = config.network

    def optional_params() -> Generator[tuple[str, Any]]:
        if net.read_timeout:
            yield "read_timeout", datetime.timedelta(seconds=net.read_timeout)
        if net.proxy:
            yield "proxies", [Proxy.all(str(net.proxy))]
        if net.impersonate:
            yield "emulation", cast_impersonate(net.impersonate)

    return WreqClient(
        http2_only=True,
        gzip=True,
        brotli=True,
        deflate=True,
        zstd=True,
        raise_for_status=False,
        dns_options=DnsOptions(system_dns=True),
        tls_min_version=cast_tls(net.tls.min_version),
        tls_verify=net.tls.verify and CertStore.from_der_certs(wassima.root_der_certificates()),
        connect_timeout=datetime.timedelta(seconds=net.connection_timeout),
        cookie_store=True,
        redirect=redirect.Policy.limited(8),
        user_agent=net.user_agent,
        tls_verify_hostname=net.tls.verify,
        **dict(optional_params()),
    )


def make_simple_cookie(cookie: Cookie, now: float) -> SimpleCookie:
    simple_cookie = SimpleCookie()
    assert cookie.value is not None
    simple_cookie[cookie.name] = cookie.value
    morsel = simple_cookie[cookie.name]
    morsel["domain"] = cookie.domain
    morsel["path"] = cookie.path
    morsel["secure"] = cookie.secure
    if cookie.expires:
        morsel["max-age"] = str(max(0, int(cookie.expires.timestamp() - now)))
    else:
        morsel["max-age"] = ""
    return simple_cookie
