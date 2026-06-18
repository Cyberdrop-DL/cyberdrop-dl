import importlib.util
import logging
from collections.abc import Iterable
from typing import Annotated, Any, override

from cyclopts import Parameter
from pydantic import BeforeValidator, Field, Secret

from cyberdrop_dl.models import AliasModel, AppriseURL
from cyberdrop_dl.models.validators import falsy_as_none

logger = logging.getLogger(__name__)

_HAS_APPRISE = importlib.util.find_spec("apprise") is not None


def _censor(value: object) -> object:
    if value and isinstance(value, str):
        return Secret(value)
    return value


@Parameter(show=False)
class CensoredModel(AliasModel):
    @override
    def __repr_name__(self) -> str:
        return ""

    @override
    def __repr__(self) -> str:
        return f"{{{self.__repr_str__(', ')}}}"

    @override
    def __repr_args__(self) -> Iterable[tuple[str | None, Any]]:
        for name, value in super().__repr_args__():
            yield name, _censor(value)


class ApiKeyAuth(CensoredModel):
    api_key: str | None = None


class EmailAuth(CensoredModel):
    email: str | None = None
    password: str | None = None


class JDownloaderAuth(CensoredModel):
    username: str | None = None
    password: str | None = None
    device: str | None = None


class Authentication(AliasModel):
    gofile: ApiKeyAuth = Field(default_factory=ApiKeyAuth)
    jdownloader: JDownloaderAuth = Field(default_factory=JDownloaderAuth)
    meganz: EmailAuth = Field(default_factory=EmailAuth)
    pixeldrain: ApiKeyAuth = Field(default_factory=ApiKeyAuth)
    realdebrid: ApiKeyAuth = Field(default_factory=ApiKeyAuth)

    def censored_dump(self) -> dict[str, bool]:
        return {site: all(credentials.values()) for site, credentials in self.model_dump().items()}


class Notifications(CensoredModel):
    apprise: tuple[AppriseURL, ...] = ()
    webhook: Annotated[AppriseURL | None, BeforeValidator(falsy_as_none)] = None

    def model_post_init(self, *_) -> None:
        if self.apprise and not _HAS_APPRISE:
            logger.warning("Found apprise URLs for notifications but apprise is not installed. Ignoring")
            self.apprise = ()
