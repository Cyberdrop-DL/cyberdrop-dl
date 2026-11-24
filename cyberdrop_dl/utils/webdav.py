# https://www.rfc-editor.org/rfc/rfc4918.html

from __future__ import annotations

import dataclasses
import datetime as dt
import email.utils
from collections.abc import Generator
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from cyberdrop_dl import context
from cyberdrop_dl.utils import xml

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Mapping


_STD_PROPERTIES: Final = (
    "creationdate",
    "displayname",
    "getcontentlength",
    "getcontenttype",
    "getetag",
    "getlastmodified",
    "resourcetype",
)
_NAMESPACE: Final = ("d", "DAV:")

xml.register_namespace(*_NAMESPACE)


class Method(StrEnum):
    """WebDAV HTTP methods"""

    PROPPATCH = "PROPPATCH"
    PROPFIND = "PROPFIND"
    DELETE = "DELETE"
    COPY = "COPY"
    MOVE = "MOVE"
    MKCOL = "MKCOL"
    LOCK = "LOCK"
    UNLOCK = "UNLOCK"


@dataclasses.dataclass(slots=True)
class Resource:
    name: str
    content_type: str
    etag: str
    last_modified: dt.datetime
    creation_date: dt.datetime

    href: str

    type: str | None
    content_length: int | None
    extra_props: dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def is_collection(self) -> bool:
        return self.type == "collection"


def parse_propfind(xml_resp: str) -> Generator[Resource]:
    for response in xml.XML(xml_resp).iterfind(".//{DAV:}response"):
        href = xml.select(response, "{DAV:}href")
        props = dict(_parse_properties(response))
        pop = props.pop

        yield Resource(
            name=pop("{DAV:}displayname"),
            content_type=pop("{DAV:}getcontenttype"),
            etag=pop("{DAV:}getetag").strip('"'),
            type=pop("{DAV:}resourcetype", None) or None,
            creation_date=dt.datetime.fromisoformat(pop("{DAV:}creationdate")),
            last_modified=email.utils.parsedate_to_datetime(pop("{DAV:}getlastmodified")),
            content_length=int(pop("{DAV:}getcontentlength", 0)) or None,
            extra_props=props,
            href=xml.text(href),
        )


def _parse_properties(response: xml.Element) -> Generator[tuple[str, str]]:
    for propstat in response.iterfind(".//{DAV:}prop"):
        for ele in propstat:
            yield ele.tag, xml.text(ele)


def create_propfind_xml(
    *extra_props: str,
    namespaces: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
) -> xml.Element:
    ns: dict[str, str] = dict([_NAMESPACE])
    if namespaces is not None:
        ns.update(namespaces)

    root = xml.Element(
        "d:propfind",
        attrib={f"xmlns:{prefix}": uri for prefix, uri in ns.items()},
    )

    props = tuple(dict.fromkeys((*_STD_PROPERTIES, *extra_props)))
    prop_element = xml.SubElement(root, "d:prop")
    for prop in props:
        _ = xml.SubElement(prop_element, f"d:{prop}" if ":" not in prop else prop)

    xml.indent(root, space="  ")
    return root


def update_tags_from_ns(root: xml.Element) -> xml.Element:
    return xml.XML(xml.to_bytes(root))


with context.enter(context.CHECK_BLOCKING_OPERATION, False):
    DEFAULT_PROPFIND = xml.to_bytes(create_propfind_xml())
