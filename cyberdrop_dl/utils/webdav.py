# https://www.rfc-editor.org/rfc/rfc4918.html

from __future__ import annotations

import dataclasses
import datetime
import email.utils
from collections.abc import Generator
from enum import StrEnum
from typing import TYPE_CHECKING, Final
from xml.etree import ElementTree as ET

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

ET.register_namespace(*_NAMESPACE)


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
    last_modified: datetime.datetime
    creation_date: datetime.datetime

    href: str

    type: str | None
    content_length: int | None
    extra_props: dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def is_collection(self) -> bool:
        return self.type == "collection"


def parse_propfind(xml_resp: str) -> Generator[Resource]:
    root = ET.fromstring(xml_resp)

    for response in root.iterfind(".//{DAV:}response"):
        href = response.find("{DAV:}href")
        assert href is not None
        assert href.text is not None

        props = dict(_parse_properties(response))

        pop = props.pop

        yield Resource(
            name=pop("{DAV:}displayname"),
            content_type=pop("{DAV:}getcontenttype"),
            etag=pop("{DAV:}getetag").strip('"'),
            type=pop("{DAV:}resourcetype", None) or None,
            creation_date=datetime.datetime.fromisoformat(pop("{DAV:}creationdate")),
            last_modified=email.utils.parsedate_to_datetime(pop("{DAV:}getlastmodified")),
            content_length=int(pop("{DAV:}getcontentlength", 0)) or None,
            extra_props=props,
            href=href.text,
        )


def _parse_properties(response: ET.Element[str]) -> Generator[tuple[str, str]]:
    for propstat in response.iterfind(".//{DAV:}prop"):
        for ele in propstat:
            if ele.text is not None:
                yield ele.tag, ele.text


def create_propfind_xml(
    *extra_props: str,
    namespaces: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
) -> ET.Element[str]:
    ns: dict[str, str] = dict([_NAMESPACE])
    if namespaces is not None:
        ns.update(namespaces)

    root = ET.Element(
        "d:propfind",
        attrib={f"xmlns:{prefix}": uri for prefix, uri in ns.items()},
    )

    props = tuple(dict.fromkeys((*_STD_PROPERTIES, *extra_props)))
    prop_element = ET.SubElement(root, "d:prop")
    for prop in props:
        _ = ET.SubElement(prop_element, f"d:{prop}" if ":" not in prop else prop)

    ET.indent(root, space="  ")
    return root


def update_tags_from_ns(root: ET.Element[str]) -> ET.Element[str]:
    return ET.fromstring(xml_to_bytes(root))


def xml_to_bytes(root: ET.Element[str]) -> bytes:
    return ET.tostring(root, xml_declaration=True, encoding="utf-8")


DEFAULT_PROPFIND = xml_to_bytes(create_propfind_xml())
