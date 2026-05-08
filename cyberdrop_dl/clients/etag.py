from collections.abc import Mapping
from http import HTTPStatus

from cyberdrop_dl.exceptions import DownloadError

_DOWNLOAD_ERROR_ETAGS = {
    "d835884373f4d6c8f24742ceabe74946": "Imgur image has been removed",
    "65b7753c-528a": "SC Scrape Image",
    "5c4fb843-ece": "PixHost Removed Image",
    "637be5da-11d2b": "eFukt Video removed",
    "63a05f27-11d2b": "eFukt Video removed",
    "5a56b09d-1485eb": "eFukt Video removed",
    "19fdf2cd6-383c-5a4cd5b6710ed": "ImageVenue image not Found",
    "383c-5a4cd5b6710ed": "ImageVenue image not Found",
}


def check(headers: Mapping[str, str]) -> None:
    e_tag = headers.get("ETag", "").strip('"')
    if message := _DOWNLOAD_ERROR_ETAGS.get(e_tag):
        raise DownloadError(HTTPStatus.NOT_FOUND, message)
