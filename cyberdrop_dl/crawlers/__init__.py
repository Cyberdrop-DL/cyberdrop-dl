from __future__ import annotations

import importlib
import pkgutil
import re
import weakref
from collections.abc import Callable
from contextvars import ContextVar
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.url_objects import AbsoluteHttpURL, is_absolute_http_url
from cyberdrop_dl.utils import remove_trailing_slash

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from types import ModuleType

    from cyberdrop_dl.crawlers.crawler import Crawler


ALLOW_NO_EXT: ContextVar[bool] = ContextVar("ALLOW_NO_EXT", default=False)
SKIP_DOWNLOAD: ContextVar[bool] = ContextVar("SKIP_DOWNLOAD", default=False)


def create_crawlers[CrawlerT: Crawler](
    urls: Iterable[str] | Iterable[AbsoluteHttpURL], base_crawler: type[CrawlerT]
) -> set[type[CrawlerT]]:
    """Creates new subclasses of the base crawler from the urls"""
    return {_create_subclass(url, base_crawler) for url in urls}


def _create_subclass[CrawlerT: Crawler](url: AbsoluteHttpURL | str, base_class: type[CrawlerT]) -> type[CrawlerT]:
    url = AbsoluteHttpURL(url)
    assert is_absolute_http_url(url)
    primary_url = remove_trailing_slash(url)
    domain = primary_url.host.removeprefix("www.")
    class_name = _make_crawler_name(domain)
    class_attributes = {
        "PRIMARY_URL": primary_url,
        "DOMAIN": domain,
        "SUPPORTED_DOMAINS": (),
        "FOLDER_DOMAIN": "",
    }
    return type(class_name, (base_class,), class_attributes)  # pyright: ignore[reportReturnType]


def _make_crawler_name(input_string: str) -> str:
    clean_string = re.sub(r"[^a-zA-Z0-9]+", " ", input_string).strip()
    cap_name = clean_string.title().replace(" ", "")
    msg = f"Can not generate a valid class name from {input_string}. Needs to be defined as a concrete class"
    assert cap_name, msg
    assert cap_name.isalnum(), msg
    if cap_name[0].isdigit():
        cap_name = "_" + cap_name
    return f"{cap_name}Crawler"


type DBFix = Callable[[str], str]


class Registry:
    abc: weakref.WeakSet[type[Crawler]] = weakref.WeakSet()
    concrete: weakref.WeakSet[type[Crawler]] = weakref.WeakSet()
    generic: weakref.WeakSet[type[Crawler]] = weakref.WeakSet()
    _db_fixes: weakref.WeakKeyDictionary[type[Crawler], DBFix | None] = weakref.WeakKeyDictionary()
    names: ClassVar[set[str]] = set()
    # generics are concrete crawlers that are not bound to any specific site
    # They can be mapped to a site by just subclassing and setting a PRIMARY URL. ex: Chevereto

    _loaded: bool = False

    @classmethod
    def import_all(cls) -> None:
        if cls._loaded:
            return

        assert __package__
        module = importlib.import_module(__package__)
        errors = tuple(cls._import_from(module))
        if errors:
            error = RuntimeError("cyberdrop-dl installation is corrupted")
            error.add_note("A complete uninstall and reinstall should fix crawler import errors")
            raise BaseExceptionGroup("", (*errors, error))

        cls._loaded = True

    @classmethod
    def _import_from(cls, module: ModuleType) -> Generator[ImportError]:
        """Import every module (and sub-package) inside *pkg_name*."""
        for sub_module_info in pkgutil.iter_modules(module.__path__, module.__name__ + "."):
            try:
                sub_module = cls._import_module(sub_module_info.name)
            except ImportError as e:
                yield e
            else:
                if sub_module_info.ispkg:
                    yield from cls._import_from(sub_module)

    @classmethod
    def _import_module(cls, name: str, /) -> ModuleType:
        try:
            return importlib.import_module(name)
        except ImportError as e:
            msg = f"Could not import crawlers from module '{name}' [{e.msg}]"
            raise ImportError(msg).with_traceback(e.__traceback__) from None

    @classmethod
    def get_crawlers(
        cls,
        *,
        concrete: bool = True,
        generic: bool = False,
        abc: bool = False,
    ) -> Generator[type[Crawler]]:
        cls.import_all()
        if concrete:
            yield from cls.concrete
        if generic:
            yield from cls.generic
        if abc:
            yield from cls.abc

    class database:  # noqa: N801
        @staticmethod
        def fix_referer[T: Crawler](crawler: type[T]) -> type[T]:
            Registry._db_fixes[crawler] = None
            return crawler

        @staticmethod
        def referer_fix_for[T: DBFix](crawler: type[Crawler]) -> Callable[[T], T]:
            def register(fn: T) -> T:
                Registry._db_fixes[crawler] = fn
                return fn

            return register

    @classmethod
    def db_fixes(cls) -> list[tuple[type[Crawler], DBFix | None]]:
        cls.import_all()
        return sorted(cls._db_fixes.items(), key=lambda x: x[0].DOMAIN.casefold())
