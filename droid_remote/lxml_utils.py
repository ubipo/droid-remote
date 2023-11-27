from lxml import etree
from typing import Optional


def elements_xpath(root: etree._Element, xpath: str) -> list[etree._Element]:
    xpath_res = root.xpath(xpath)
    if not isinstance(xpath_res, list):
        raise Exception(f"Expected xpath result to be a list, got {str(xpath_res)}")
    return [e for e in xpath_res if isinstance(e, etree._Element)]


def attrib(
    element: etree._Element, attrib_name: str, default: Optional[str] = None
) -> Optional[str]:
    attrib_value = element.attrib.get(attrib_name)
    if attrib_value is None:
        return default
    if isinstance(attrib_value, bytes):
        return attrib_value.decode()
    return attrib_value


def attrib_or_error(
    element: etree._Element,
    attrib_name: str,
) -> str:
    attrib_value = attrib(element, attrib_name)
    if attrib_value is None:
        raise ValueError(f"Element {element.tag} does not have attribute {attrib_name}")
    return attrib_value


def element_to_string(element):
    return etree.tostring(element, pretty_print=True).decode()
