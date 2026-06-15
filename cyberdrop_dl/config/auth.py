import importlib.util
import logging
from typing import Annotated

from cyclopts import Parameter
from pydantic import BeforeValidator, Field

from cyberdrop_dl.models import AliasModel, AppriseURL
from cyberdrop_dl.models.validators import falsy_as_none

logger = logging.getLogger(__name__)

_HAS_APPRISE = importlib.util.find_spec("apprise") is not None


class ApiKeyAuth(AliasModel):
    api_key: str = ""


class EmailAuth(AliasModel):
    email: str = ""
    password: str = ""


class JDownloaderAuth(AliasModel):
    username: str = ""
    password: str = ""
    device: str = ""


@Parameter(show=False)
class AuthSettings(AliasModel):
    gofile: ApiKeyAuth = Field(default_factory=ApiKeyAuth)
    jdownloader: JDownloaderAuth = Field(default_factory=JDownloaderAuth)
    meganz: EmailAuth = Field(default_factory=EmailAuth)
    pixeldrain: ApiKeyAuth = Field(default_factory=ApiKeyAuth)
    realdebrid: ApiKeyAuth = Field(default_factory=ApiKeyAuth)


@Parameter(show=False)
class Notifications(AliasModel):
    apprise: tuple[AppriseURL, ...] = ()
    webhook: Annotated[AppriseURL | None, BeforeValidator(falsy_as_none)] = None

    def model_post_init(self, *_) -> None:
        if self.apprise and not _HAS_APPRISE:
            logger.warning("Found apprise URLs for notifications but apprise is not installed. Ignoring")
            self.apprise = ()
