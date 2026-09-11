"""Regression tests for how a model's reply is turned into result indices.

Three defects lived here: the label stripper took the LAST colon, the range
regex let \s* cross newlines, and markdown list markers were scanned as
indices. Each one silently changed which results the user was shown.
"""
import unittest

import llm


class LabelStripping(unittest.TestCase):
    def test_trailing_reasoning_line_does_not_replace_the_selection(self):
        reply = "Indices: 3, 9, 12\nReasoning: these match the 2024 breach discussion"
        self.assertEqual(list(llm._iter_selected_indices(llm._strip_leading_label(reply))), [3, 9, 12])

    def test_trailing_url_does_not_replace_the_selection(self):
        reply = "Selected: 3, 9\nNote: see http://abc.onion/page1"
        self.assertEqual(list(llm._iter_selected_indices(llm._strip_leading_label(reply))), [3, 9])

    def test_leading_label_is_still_stripped(self):
        self.assertEqual(llm._strip_leading_label("Top 5 results, ranked by relevance: 3, 9, 12").strip(), "3, 9, 12")

    def test_label_on_its_own_line(self):
        self.assertEqual(llm._strip_leading_label("Selected indices:\n1, 4, 9").strip(), "1, 4, 9")

    def test_json_reply(self):
        self.assertIn("[2, 5, 9]", llm._strip_leading_label('{"indices": [2, 5, 9]}'))

    def test_indices_before_a_colon_are_left_alone(self):
        self.assertEqual(llm._strip_leading_label("1, 2, 3: my picks"), "1, 2, 3: my picks")


class IndexScanning(unittest.TestCase):
    def test_bulleted_reply_is_not_read_as_a_range(self):
        self.assertEqual(list(llm._iter_selected_indices("- 3\n- 9\n- 12")), [3, 9, 12])

    def test_numbered_reply_does_not_contribute_its_own_ordinals(self):
        self.assertEqual(list(llm._iter_selected_indices("1. 3\n2. 9\n3. 12")), [3, 9, 12])

    def test_numbered_reply_with_prose(self):
        reply = "1. Index 3 - Forum thread\n2. Index 9 - Leak listing"
        self.assertEqual(list(llm._iter_selected_indices(reply)), [3, 9])

    def test_real_ranges_still_expand(self):
        self.assertEqual(list(llm._iter_selected_indices("1-5")), [1, 2, 3, 4, 5])
        self.assertEqual(list(llm._iter_selected_indices("10 - 12")), [10, 11, 12])

    def test_plain_comma_list(self):
        self.assertEqual(list(llm._iter_selected_indices("3, 9, 12")), [3, 9, 12])


if __name__ == "__main__":
    unittest.main()
