"""Generic crawler for any Invision forum

A Invision site has a tag with a `ipsCopyright` class and the text: "Powered By Invision"
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._forum import HTMLMessageBoardCrawler
from cyberdrop_dl.crawlers.xenforo.xenforo import DEFAULT_XF_POST_SELECTORS, DEFAULT_XF_SELECTORS, XenforoCrawler
from cyberdrop_dl.utils import css

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers._forum import MessageBoardSelectors
    from cyberdrop_dl.crawlers.crawler import SupportedPaths


DEFAULT_INVISION_POST_SELECTORS = dataclasses.replace(
    DEFAULT_XF_POST_SELECTORS,
    article="div[class*=ipsComment_content]",
    content="div.cPost_contentWrap",
    article_trash=(".message-signature", ".message-footer"),
    content_trash=("blockquote", "fauxBlockLink"),
    id=css.Selector("data-commentid", "data-commentid"),
    attachments=css.Selector("a[class*=ipsAttachLink]", "href"),
    images=css.Selector("a[class*=ipsAttachLink_image]", "href"),
    videos=css.Selector("video.ipsEmbeddedVideo source", "src"),
)


DEFAULT_INVISION_SELECTORS = dataclasses.replace(
    DEFAULT_XF_SELECTORS,
    posts=DEFAULT_INVISION_POST_SELECTORS,
    title=css.Selector("span.ipsType_break.ipsContained span"),
    next_page=css.Selector("li.ipsPagination_next a[href]", "href"),
)


class InvisionCrawler(HTMLMessageBoardCrawler, is_abc=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = XenforoCrawler.SUPPORTED_PATHS | {"**NOTE**": "base crawler: Invision"}
    SUPPORTS_THREAD_RECURSION: ClassVar[bool] = True
    SELECTORS: ClassVar[MessageBoardSelectors] = DEFAULT_INVISION_SELECTORS  # pyright: ignore[reportAssignmentType]
    POST_URL_PART_NAME: ClassVar[str] = "comment"
    PAGE_URL_PART_NAME: ClassVar[str] = "page"
    IGNORE_EMBEDED_IMAGES_SRC: ClassVar[bool] = False
    LOGIN_USER_COOKIE_NAME: ClassVar[str] = "UNKNOWN"  # TODO: Find out cookie name
    ATTACHMENT_HOSTS: ClassVar[tuple[str, ...]] = ()
