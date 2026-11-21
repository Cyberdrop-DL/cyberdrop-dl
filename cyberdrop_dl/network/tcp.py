from __future__ import annotations

import base64
import functools
import logging
import ssl
from typing import TYPE_CHECKING

import aiohttp
import wassima

from cyberdrop_dl.utils import TextExtractor

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from pathlib import Path


logger = logging.getLogger(__name__)


def create_connector(ssl_context: ssl.SSLContext | bool, /) -> aiohttp.TCPConnector:  # noqa: FBT001
    tcp_conn = aiohttp.TCPConnector(
        ssl=ssl_context,
        resolver=aiohttp.ThreadedResolver(),
        use_dns_cache=True,
        ttl_dns_cache=1_000,
        limit=200,
    )
    tcp_conn._resolver_owner = True
    return tcp_conn


def create_ssl_context(
    min_ver: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2,
    ca_certs: Iterable[Path] = (),
) -> ssl.SSLContext:
    for file in _list_pem_files(ca_certs):
        _register_pem_file(file)
    ctx = wassima.create_default_ssl_context(hybrid_store=True)
    ctx.minimum_version = min_ver
    return ctx


def resolve_tls_version(name: str) -> ssl.TLSVersion:
    match name:
        case "1.2":
            return ssl.TLSVersion.TLSv1_2
        case "1.3":
            return ssl.TLSVersion.TLSv1_3
        case _:
            raise ValueError(name)


def _list_pem_files(paths: Iterable[Path]) -> Generator[Path]:
    for path in paths:
        if path.is_dir():
            yield from _list_pem_files(path.glob("*.pem"))
        elif path.suffix != ".pem":
            logger.warning("'%s' is not a valid PEM file, ignoring..", path)
            continue
        else:
            yield path


@functools.cache
def root_der_certificates() -> set[bytes]:
    return set(wassima.root_der_certificates())


def _register_pem_file(file: Path) -> None:
    logger.debug("Loading certificates from '%s'", file)

    loaded, total = _load_cert_chain(file)
    if loaded == total:
        logger.warning("None of the certificates (%s) in the chain from '%s' are trusted by the OS", total, file)
    else:
        skipped = total - loaded
        logger.debug(
            "Loaded %s certificates from '%s'%s",
            loaded,
            file,
            f" ({total - loaded} skipped as {'they were' if skipped > 1 else 'it was'} already trusted by the OS)"
            if skipped
            else "",
        )


def _load_cert_chain(file: Path) -> tuple[int, int]:
    certs = tuple(_read_cert_chain(file))
    if not certs:
        raise ValueError(f"No valid certificates found in '{file}'")

    trusted_cas = root_der_certificates()
    for idx, cert in enumerate(certs):
        if cert in trusted_cas:
            return idx, len(certs)
        wassima.register_ca(cert)

    return len(certs), len(certs)


def _read_cert_chain(path: Path) -> Generator[bytes]:
    for cert in TextExtractor(path.read_text()).repeat(ssl.PEM_HEADER, ssl.PEM_FOOTER):
        yield base64.decodebytes(cert.encode("ascii", "strict"))
