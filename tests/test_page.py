from html.parser import HTMLParser
from importlib.resources import files
import json
import unittest

from yaml_cfg_wizard_ui import render_page


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.config = ""
        self.in_config = False

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self.in_config = tag == "script" and dict(attrs).get("id") == "editor-config"

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_config = False

    def handle_data(self, data):
        if self.in_config:
            self.config += data


class PageTests(unittest.TestCase):
    def page(self, **options):
        return render_page(endpoint="/api/editor", csrf_token="csrf", **options)

    def test_hostile_configuration_is_inert_json(self):
        attack = '</script><img src=x onerror="alert(1)">&\u2028${js}'
        page = render_page(endpoint="/api/editor", csrf_token=attack.replace("\u2028", "X").replace(" ", ""),
                           title=attack, description=attack, saved_message=attack,
                           fields={attack: {"type": ["string", "null"]}}, script_nonce="abc123")
        parser = PageParser()
        parser.feed(page)
        config = json.loads(parser.config)
        self.assertEqual(config["title"], attack)
        self.assertEqual(config["fields"][attack]["type"], ["string", "null"])
        self.assertNotIn("<", parser.config)
        self.assertNotIn(">", parser.config)
        self.assertNotIn("&", parser.config)
        self.assertEqual(len([tag for tag, _ in parser.tags if tag == "script"]), 2)
        self.assertFalse(any(tag == "img" for tag, _ in parser.tags))
        self.assertTrue(all(attrs["nonce"] == "abc123" for tag, attrs in parser.tags if tag in {"script", "style"}))

    def test_same_origin_endpoints(self):
        for endpoint in ("https://evil.test", "//evil.test", "/%2f/evil.test", "relative",
                         "/\\evil", "/%5cevil", "/api?x=1", "/api#", "/a\nb", "/%0Ab"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                render_page(endpoint=endpoint, csrf_token="csrf")
        self.assertIn("/api/editor", self.page())

    def test_tokens_and_metadata_validation(self):
        for token in ("", "a\r\nx:y", "a b", "\u2603", "\x7f"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                render_page(endpoint="/api/editor", csrf_token=token)
        for fields in ({"x": {"type": "object"}}, {"x": {"type": []}},
                       {"x": {"nullable": "true"}}, {"x": {"maxLength": -1}},
                       {"x": {"maxLength": True}}, {"x": {"unknown": 1}},
                       {"x": {"type": ["string", "string"]}}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.page(fields=fields)
        with self.assertRaises(ValueError):
            self.page(script_nonce='"><script>')

    def test_assets_and_framework_independence(self):
        assets = files("yaml_cfg_wizard_ui").joinpath("assets")
        for name in ("page.html", "editor.css", "editor.js"):
            self.assertTrue(assets.joinpath(name).is_file())
        js = assets.joinpath("editor.js").read_text()
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("eval(", js)
        page = self.page(fields={"optional": {"type": "string", "nullable": True}})
        self.assertIn("Reload configuration", page)
        self.assertIn("textContent", page)
        self.assertIn("noscript", page)


if __name__ == "__main__":
    unittest.main()
