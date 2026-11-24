from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload
from xml.etree import ElementTree as ET  # noqa: TID251

from cyberdrop_dl.utils import css

SubElement = ET.SubElement
indent = ET.indent
register_namespace = ET.register_namespace
SelectorError = css.SelectorError


def _check_running_loop() -> None:
    __tracebackhide__ = True
    css._check_running_loop("XML")


if TYPE_CHECKING:
    Element = ET.Element[str]

    XML = ET.XML
else:
    Element = ET.Element

    def XML(*args, **kwargs):  # noqa: N802
        _check_running_loop()
        return ET.XML(*args, **kwargs)


def attr_or_none(ele: ET.Element[Any], *attributes: str) -> str | None:
    for attribute in attributes:
        if ele_found := ele.attrib.get(attribute):
            return ele_found


def attr(ele: ET.Element[Any], *attributes: str) -> str:
    if ele_found := attr_or_none(ele, *attributes):
        return ele_found
    raise SelectorError(f"{attributes = } not found")


def _select_one(ele: ET.Element[Any], xpath: str) -> ET.Element:
    _check_running_loop()
    ele_found = ele.find(xpath)
    if ele_found is None:
        raise SelectorError(f"XML {xpath = } not found")
    return ele_found


@overload
def select(ele: ET.Element[Any], xpath: str) -> ET.Element: ...


@overload
def select(ele: ET.Element[Any], xpath: str, attribute: str) -> str: ...


def select(ele: ET.Element[Any], xpath: str, attribute: str | None = None) -> ET.Element | str:
    inner_ele = _select_one(ele, xpath)
    if not attribute:
        return inner_ele
    return attr(inner_ele, attribute)


def select_text(ele: ET.Element[Any], path: str) -> str:
    return text(select(ele, path))


def text(ele: ET.Element[Any]) -> str:
    return ele.text or ""


def to_bytes(
    element: ET.Element[Any],
    *,
    xml_declaration: bool | None = True,
    default_namespace: str | None = None,
    short_empty_elements: bool = True,
) -> bytes:
    _check_running_loop()
    return ET.tostring(
        element,
        xml_declaration=xml_declaration,
        method="xml",
        encoding="utf-8",
        default_namespace=default_namespace,
        short_empty_elements=short_empty_elements,
    )
