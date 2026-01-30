from typing import TYPE_CHECKING

from . import _browser_cookie3 as browser_cookie3

if TYPE_CHECKING:
    import apprise

else:
    try:
        import apprise
    except ImportError:
        apprise = None

__all__ = ["apprise", "browser_cookie3"]
