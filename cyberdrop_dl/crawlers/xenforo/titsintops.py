from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css

from .xenforo import XenforoCrawler

if TYPE_CHECKING:
    import yarl
    from bs4 import Tag


class TitsInTopsCrawler(XenforoCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://titsintops.com/phpBB2")
    DOMAIN: ClassVar[str] = "titsintops"
    FOLDER_DOMAIN: ClassVar[str] = "TitsInTops"

    @classmethod
    def parse_url(
        cls,
        url: yarl.URL | str,
        /,
        relative_to: AbsoluteHttpURL | None = None,
        *,
        trim: bool | None = None,
    ) -> AbsoluteHttpURL:
        return super().parse_url(_query_to_path(str(url)), relative_to, trim=trim)

    def is_username_or_attachment(self, link_obj: Tag) -> bool:
        text = css.text(link_obj)
        if "view attachment" in text.lower():
            return True
        title = css.attr_or_none(link_obj, "title")
        if title and "permanent link" in title.lower():
            return True
        return super().is_username_or_attachment(link_obj)


def _query_to_path(link: str) -> str:
    return (
        link.replace("index.php%3F", "index.php/")
        .replace("index.php?", "index.php/")
        .replace("index.php?goto", "index.php/goto")
    )
