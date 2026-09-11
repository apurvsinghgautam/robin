"""Regression tests for unwrapping a search engine's redirect links.

A raw regex scan absorbed the engine's own trailing query parameters into the
extracted target, producing URLs that 404 on the target host and key
differently from the clean URL in dedup.
"""
import unittest

import search

ENGINE = "engine7abcdefghij.onion"


def extract(href):
    return search._extract_target_onion(href, ENGINE)


class RedirectUnwrapping(unittest.TestCase):
    def test_plain_wrapper_drops_engine_parameters(self):
        href = "/search/redirect?redirect_url=http://target7abcdefghij.onion/&search_term=x"
        self.assertEqual(extract(href), "http://target7abcdefghij.onion/")

    def test_percent_encoded_wrapper_keeps_the_target_query_only(self):
        href = "/search/redirect?redirect_url=http%3A%2F%2Ftarget.onion%2Fthread%3Fid%3D5&search_term=ransomware"
        self.assertEqual(extract(href), "http://target.onion/thread?id=5")

    def test_absolute_wrapper_on_the_engine_host(self):
        href = f"http://{ENGINE}/out?u=http://target.onion/page&ref=1"
        self.assertEqual(extract(href), "http://target.onion/page")


class DirectLinksAreUnchanged(unittest.TestCase):
    def test_target_own_query_parameters_survive(self):
        href = "http://target.onion/page?a=1&b=2"
        self.assertEqual(extract(href), href)

    def test_plain_external_result(self):
        self.assertEqual(extract("http://other.onion/thread"), "http://other.onion/thread")


class EngineNavigationIsStillDropped(unittest.TestCase):
    def test_relative_internal_link(self):
        self.assertIsNone(extract("/about"))

    def test_absolute_internal_link(self):
        self.assertIsNone(extract(f"http://{ENGINE}/faq"))

    def test_empty_href(self):
        self.assertIsNone(extract(""))


if __name__ == "__main__":
    unittest.main()
