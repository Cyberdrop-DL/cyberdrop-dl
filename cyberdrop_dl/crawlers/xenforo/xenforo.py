"""Generic crawler for any Xenforo

A Xenforo site has these attributes attached to the main html tag of the site:
id="XF"                                  This identifies the site as a Xenforo site
data-cookie-prefix="ogaddgmetaprof_"     The full cookies name will be `ogaddgmetaprof_user`
data-xf="2.3"                            Version number


Xenforo sites have a REST API but the APi is private only. Admins of the site need to grand access user by user
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._forum import HTMLMessageBoardCrawler, MessageBoardSelectors, PostSelectors
from cyberdrop_dl.utils import css

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cyberdrop_dl.crawlers.crawler import SupportedPaths


Selector = css.CssAttributeSelector


DEFAULT_XF_POST_SELECTORS = PostSelectors(
    article="article.message[id*=post]",
    content=".message-userContent",
    article_trash=(".message-signature", ".message-footer"),
    content_trash=("blockquote", "fauxBlockLink"),
    id=Selector("article.message[id*=post]", "id"),
    attachments=Selector(".message-attachments a[href]", "href"),
)


DEFAULT_XF_SELECTORS = MessageBoardSelectors(
    posts=DEFAULT_XF_POST_SELECTORS,
    confirmation_button=Selector("a[class*=button--cta][href]", "href"),
    next_page=Selector("a[class*=pageNav-jump--next][href]", "href"),
    title_trash=("span",),
    title=Selector("h1[class*=p-title-value]"),
    last_page=Selector("li.pageNav-page a:last-of-type", "href"),
    current_page=Selector("li.pageNav-page.pageNav-page--current a", "href"),
)


class XenforoCrawler(HTMLMessageBoardCrawler, is_abc=True):
    ATTACHMENT_URL_PARTS: ClassVar[tuple[str, ...]] = "attachments", "data", "uploads"
    THREAD_PART_NAMES: ClassVar[Sequence[str]] = "thread", "topic", "tema", "threads", "topics", "temas"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Attachments": f"/{'|'.join(ATTACHMENT_URL_PARTS)}/...",
        "Threads": (
            f"/{'|'.join(THREAD_PART_NAMES)}/<thread_name_and_id>",
            "/posts/<post_id>",
            "/goto/<post_id>",
        ),
        "**NOTE**": "base crawler: Xenforo",
    }
    SUPPORTS_THREAD_RECURSION: ClassVar[bool] = True
    SELECTORS: ClassVar[MessageBoardSelectors] = DEFAULT_XF_SELECTORS
    POST_URL_PART_NAME: ClassVar[str] = "post"
    PAGE_URL_PART_NAME: ClassVar[str] = "page"
    IGNORE_EMBEDED_IMAGES_SRC: ClassVar[bool] = True
    LOGIN_USER_COOKIE_NAME: ClassVar[str] = "xf_user"
    _FORUM: ClassVar[bool] = True
    # Attachments hosts should technically be defined on each specific Crawler, but they do no harm here
    ATTACHMENT_HOSTS = "smgmedia", "attachments.f95zone"
    login_required = True
