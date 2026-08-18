from __future__ import annotations

from typing import TYPE_CHECKING, Any

import wassima

if TYPE_CHECKING:
    from collections.abc import Generator

    from wreq import Client  # pyright: ignore[reportPrivateImportUsage]
    from wreq.cookie import Jar
    from wreq.emulation import Emulation, Profile

    from cyberdrop_dl.config import Config
    from cyberdrop_dl.constants import ImpersonateTarget


def resolve_impersonate(target: ImpersonateTarget) -> Emulation | Profile:
    from wreq.emulation import Emulation, Platform

    return {
        "chrome": Emulation.Chrome149,
        "edge": Emulation.Edge148,
        "safari": Emulation.Safari26_4,
        "safari_ios": Emulation.SafariIos26_2,
        "chrome_android": Emulation(Emulation.Chrome149, Platform.Android),
        "firefox": Emulation.Firefox151,
    }[target]


async def create_client(config: Config) -> tuple[Client, Jar]:
    from wreq import Client, redirect  # pyright: ignore[reportPrivateImportUsage]
    from wreq.cookie import Jar
    from wreq.dns import DnsOptions
    from wreq.proxy import Proxy
    from wreq.tls import CertStore, TlsVersion

    net = config.network
    tls = f"TLS_{net.tls.min_version.replace('.', '_')}"
    import datetime

    def optional_params() -> Generator[tuple[str, Any]]:
        if net.read_timeout:
            yield "read_timeout", datetime.timedelta(seconds=net.read_timeout)
        if net.proxy:
            yield "proxies", [Proxy.all(str(net.proxy))]
        if net.impersonate:
            yield "emulation", resolve_impersonate(net.impersonate)

    cookie_jar = Jar()
    client = Client(
        http2_only=True,
        gzip=True,
        brotli=True,
        deflate=True,
        zstd=True,
        raise_for_status=False,
        dns_options=DnsOptions(system_dns=True),
        tls_min_version=TlsVersion[tls],
        tls_verify=net.tls.verify and CertStore.from_der_certs(wassima.root_der_certificates()),
        connect_timeout=datetime.timedelta(seconds=net.connection_timeout),
        cookie_store=True,
        cookie_provider=cookie_jar,
        redirect=redirect.Policy.limited(8),
        user_agent=net.user_agent,
        **dict(optional_params()),
    )

    return client, cookie_jar
