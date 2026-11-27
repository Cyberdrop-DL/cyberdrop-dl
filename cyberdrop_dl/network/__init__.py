import logging

from aiohttp import hdrs
from multidict import istr

from cyberdrop_dl import signature
from cyberdrop_dl.constants import HttpMethod as HttpMethod
from cyberdrop_dl.logs import LOG_HTTP_TRAFFIC


class TrafficLogger(logging.LoggerAdapter[logging.Logger]):
    @signature.copy(logging.LoggerAdapter.info)
    def traffic(self, msg, *args, **kwargs) -> None:
        if LOG_HTTP_TRAFFIC.get():
            self.log(logging.INFO, msg, *args, **kwargs)


def get_logger(name: str) -> TrafficLogger:
    return TrafficLogger(logging.getLogger(name))


# dict instead of set to preserve ordering
AUTH_HEADERS: dict[str, None] = dict.fromkeys(
    (
        hdrs.AUTHORIZATION,
        hdrs.AUTHENTICATION_INFO,
        hdrs.COOKIE,
        hdrs.PROXY_AUTHORIZATION,
        hdrs.PROXY_AUTHENTICATE,
        hdrs.PROXY_AUTHENTICATION_INFO,
        istr("API_KEY"),
        istr("APIKEY"),
        istr("API-KEY"),
    )
)


def register_headers_to_censor(*headers: str) -> None:
    AUTH_HEADERS.update(dict.fromkeys(headers))
