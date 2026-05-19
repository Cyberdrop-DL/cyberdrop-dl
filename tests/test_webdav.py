from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

import pytest

from cyberdrop_dl import signature
from cyberdrop_dl.utils import webdav

if TYPE_CHECKING:
    from xml.etree import ElementTree as ET

XML = """<?xml version="1.0"?>
<d:multistatus
    xmlns:d="DAV:"
    xmlns:oc="http://owncloud.org/ns"
    xmlns:nc="http://nextcloud.org/ns">
    <d:response>
        <d:href>/public.php/dav/files/e5mYoDxSSGn2b</d:href>
        <d:propstat>
            <d:prop>
                <d:displayname>movie.mp4</d:displayname>
                <d:getcontenttype>video/mp4</d:getcontenttype>
                <d:resourcetype/>
                <d:getetag>&quot;ac8d5ef02ce089df735bf8c3813be492&quot;</d:getetag>
                <d:getcontentlength>422682383</d:getcontentlength>
                <d:getlastmodified>Fri, 27 Mar 2026 22:03:10 GMT</d:getlastmodified>
                <d:creationdate>1970-01-01T00:00:00+00:00</d:creationdate>
            </d:prop>
            <d:status>HTTP/1.1 200 OK</d:status>
        </d:propstat>
    </d:response>
</d:multistatus>
"""


def test_webdav_parse_propfind() -> None:
    resources = tuple(webdav.parse_propfind(XML))
    assert len(resources) == 1
    assert resources[0] == webdav.Resource(
        name="movie.mp4",
        content_type="video/mp4",
        type=None,
        etag="ac8d5ef02ce089df735bf8c3813be492",
        content_length=422682383,
        last_modified=datetime.datetime(2026, 3, 27, 22, 3, 10, tzinfo=datetime.UTC),
        creation_date=datetime.datetime(1970, 1, 1, 0, 0, tzinfo=datetime.UTC),
        href="/public.php/dav/files/e5mYoDxSSGn2b",
    )


class TestPropFind:
    @staticmethod
    @signature.copy(webdav.create_propfind_xml)
    def create_propfind_xml(*args: Any, **kwargs: Any) -> ET.Element[str]:
        root = webdav.create_propfind_xml(*args, **kwargs)
        return webdav.update_tags_from_ns(root)

    @staticmethod
    def prop(root: ET.Element[str]) -> ET.Element[str]:
        prop = root.find("{DAV:}prop")
        assert prop is not None
        return prop

    def test_default_propfind(self) -> None:
        root = self.create_propfind_xml()
        assert root.tag == "{DAV:}propfind"
        prop = self.prop(root)
        name_ele = prop.find("{DAV:}displayname")
        assert name_ele is not None
        assert name_ele.text is None

        tags = {element.tag for element in prop}
        expected = {"{DAV:}" + prop for prop in webdav._STD_PROPERTIES}
        assert tags == expected

    def test_additional_ns(self) -> None:
        root = self.create_propfind_xml("cs:getctag", namespaces={"cs": "https://calendarserver.org/ns"})
        prop = self.prop(root)
        assert prop.find("{https://calendarserver.org/ns}getctag") is not None

    @pytest.mark.parametrize(
        ("props", "extra_ns"),
        [
            (("displayname",), None),
            (("displayname",), {}),
            (
                ("displayname", "cs:getctag"),
                {
                    "cs": "http://calendarserver.org/ns",
                },
            ),
            (
                ("displayname", "cs:getctag", "oc:size"),
                {
                    "cs": "http://calendarserver.org/ns",
                    "oc": "http://owncloud.org/ns",
                },
            ),
        ],
    )
    def test_custom_namespaces(self, props: tuple[str, ...], extra_ns: dict[str, str] | None) -> None:
        root = self.create_propfind_xml(*props, namespaces=extra_ns)
        assert root.attrib == {}
        for prop in props:
            if ":" in prop:
                assert root.find(f".//{prop}", extra_ns) is not None

    def test_to_bytes_has_xml_declaration(self) -> None:
        assert webdav.xml_to_bytes(self.create_propfind_xml()).startswith(b"<?xml version=")
