"""Options disclosures must not expand automatically on initial render."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class OptionSections(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sections = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'details' and 'game1-option-section' in attributes.get('class', '').split():
            self.sections.append(attributes)


class OptionsCollapsedTests(unittest.TestCase):
    def test_option_sections_are_closed_by_default(self):
        parser = OptionSections()
        parser.feed((ROOT / 'system/control-center/static/index.html').read_text(encoding='utf-8'))
        self.assertTrue(parser.sections)
        self.assertTrue(all('open' not in section for section in parser.sections))
