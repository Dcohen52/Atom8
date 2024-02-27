import requests
from bs4 import BeautifulSoup, Tag
import json


def get_xpath(element):
    """
    Generate XPath for a BeautifulSoup element.
    """
    components = []
    child = element if element.name else element.parent
    for parent in child.parents:
        siblings = parent.find_all(child.name, recursive=False)
        components.append(
            child.name if siblings.index(child) == 0 else '%s[%d]' % (child.name, siblings.index(child) + 1)
        )
        child = parent
    components.reverse()
    return '/'.join(components)


def extract_elements_to_json(url):
    response = requests.get(url)
    if response.status_code != 200:
        return "Failed to retrieve the webpage."
    soup = BeautifulSoup(response.content, 'html.parser')
    elements_data = []
    for element in soup.find_all(['button', 'input', 'a']):
        if not isinstance(element, Tag):
            continue
        value = element.get_text(strip=True) or element.get('value') or element.get('placeholder') or "No value"
        element_type = element.name
        xpath = get_xpath(element)
        locator_info = {"xpath": xpath, "attributes": element.attrs}
        elements_data.append({"value": f"{value} - {element_type}", "locators": [locator_info]})

    return elements_data
