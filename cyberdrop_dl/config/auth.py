from cyclopts import Parameter
from pydantic import BaseModel, Field

from cyberdrop_dl.models import AliasModel


class CoomerAuth(BaseModel):
    session: str = ""


class ImgurAuth(AliasModel):
    client_id: str = ""


class MegaNzAuth(AliasModel):
    email: str = ""
    password: str = ""


class JDownloaderAuth(AliasModel):
    username: str = ""
    password: str = ""
    device: str = ""


class KemonoAuth(AliasModel):
    session: str = ""


class GoFileAuth(AliasModel):
    api_key: str = ""


class PixeldrainAuth(AliasModel):
    api_key: str = ""


class RealDebridAuth(AliasModel):
    api_key: str = ""


@Parameter(show=False)
class AuthSettings(AliasModel):
    coomer: CoomerAuth = Field(default_factory=CoomerAuth)
    gofile: GoFileAuth = Field(default_factory=GoFileAuth)
    imgur: ImgurAuth = Field(default_factory=ImgurAuth)
    jdownloader: JDownloaderAuth = Field(default_factory=JDownloaderAuth)
    kemono: KemonoAuth = Field(default_factory=KemonoAuth)
    meganz: MegaNzAuth = Field(default_factory=MegaNzAuth)
    pixeldrain: PixeldrainAuth = Field(default_factory=PixeldrainAuth)
    realdebrid: RealDebridAuth = Field(default_factory=RealDebridAuth)
