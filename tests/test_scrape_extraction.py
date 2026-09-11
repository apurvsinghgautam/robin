"""Regression tests for the boilerplate strip in scrape.scrape_single.

The strip list once included <form>, which deleted the entire topic table on
phpBB and SMF boards because both wrap their listing in one.
"""
import unittest

import scrape

extract = scrape.extract_page_text


PHPBB = (
    '<div id="page-header"><h1>Leaks Board</h1></div>'
    '<form id="topiclist"><ul class="topiclist topics">'
    '<li><a class="topictitle">ACME Corp 400GB database dump</a> by seller99</li>'
    '<li><a class="topictitle">Bank of X cardholder records 2.1M</a> by vendor7</li>'
    '</ul></form>'
)


class FormContentSurvives(unittest.TestCase):
    def test_phpbb_topic_listing_is_not_stripped(self):
        text = extract(PHPBB)
        self.assertIn("ACME Corp 400GB database dump", text)
        self.assertIn("Bank of X cardholder records 2.1M", text)

    def test_smf_message_index_form_survives(self):
        html = '<form name="messageindex"><td>Ransomware crew recruiting</td></form>'
        self.assertIn("Ransomware crew recruiting", extract(html))


class OverStrippingIsUndone(unittest.TestCase):
    def test_content_inside_header_is_kept_when_strip_eats_the_page(self):
        html = '<nav>Home Forums</nav><header><h1>' + 'Topic title here. ' * 20 + '</h1></header>'
        text = extract(html)
        self.assertIn("Topic title here.", text)

    def test_ordinary_page_still_loses_its_furniture(self):
        body = 'Real article body. ' * 40
        html = f'<nav>Home Forums Login</nav><div>{body}</div><footer>Powered by X</footer>'
        text = extract(html)
        self.assertIn("Real article body.", text)
        self.assertNotIn("Powered by X", text)
        self.assertNotIn("Home Forums Login", text)


if __name__ == "__main__":
    unittest.main()
