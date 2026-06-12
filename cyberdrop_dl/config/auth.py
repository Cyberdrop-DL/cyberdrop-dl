from cyclopts import Parameter
from pydantic import Field

from cyberdrop_dl.models import AliasModel


class ApiKeyAuth(AliasModel):
    api_key: str = ""


class EmailAuth(AliasModel):
    email: str = ""
    password: str = ""


class JDownloaderAuth(AliasModel):
    username: str = ""
    password: str = ""
    device: str = ""


class KemonoAuth(AliasModel):
    session: str = ""


@Parameter(show=False)
class AuthSettings(AliasModel):
    coomer: KemonoAuth = Field(default_factory=KemonoAuth)
    gofile: ApiKeyAuth = Field(default_factory=ApiKeyAuth)
    jdownloader: JDownloaderAuth = Field(default_factory=JDownloaderAuth)
    kemono: KemonoAuth = Field(default_factory=KemonoAuth)
    meganz: EmailAuth = Field(default_factory=EmailAuth)
    pixeldrain: ApiKeyAuth = Field(default_factory=ApiKeyAuth)
    realdebrid: ApiKeyAuth = Field(default_factory=ApiKeyAuth)
