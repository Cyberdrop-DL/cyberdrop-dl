"""Loads external packages dinamically from their metadata

Packages need to specify an entrypoint in their metadata as "cyberdrop_dl_plugins".

The entrypoint will be executed after CDL's startup but before the scrape process begins.

The entrypoint must be a callable that takes an instance of `Manager`

Example plugin: https://github.com/NTFSvolume/cdl-dynamic-crawlers

NOTE: Since this works with packages' metadata, only valid packages published to pypi can be used as plugins and they need to be installed on the same env as CDL

See: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-package-metadata"""

from __future__ import annotations

import dataclasses
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Final

from cyberdrop_dl import env
from cyberdrop_dl.utils.logger import log

if TYPE_CHECKING:
    from collections.abc import Iterable
    from importlib.metadata import EntryPoint

    from cyberdrop_dl.managers.manager import Manager

_GROUP_NAME: Final = "cyberdrop_dl_plugins"


@dataclasses.dataclass(slots=True, frozen=True)
class Plugin:
    name: str
    module: str
    value: str
    entrypoint: EntryPoint = dataclasses.field(repr=False)


def _get_plugins() -> Iterable[Plugin]:
    for entrypoint in entry_points(group=_GROUP_NAME):
        yield Plugin(
            entrypoint.name,
            entrypoint.module,
            entrypoint.value,
            entrypoint,
        )


def load(manager: Manager) -> None:
    for plugin in _get_plugins():
        if env.NO_PLUGINS:
            log(f"Found plugins installed but plugins are disabled. Ignored: {tuple(_get_plugins())}", 40)
            return

        plugin.entrypoint.load()(manager)
        log(f"Loaded {plugin}", 20)
