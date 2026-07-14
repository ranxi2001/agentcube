#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("maintainer_review_history.py")
SPEC = importlib.util.spec_from_file_location("maintainer_review_history", SCRIPT)
assert SPEC and SPEC.loader
HISTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HISTORY)


class MaintainerReviewHistoryTest(unittest.TestCase):
    def test_collects_reviewer_comments_and_author_replies(self) -> None:
        comments = [
            {
                "id": 10,
                "user": {"login": "Reviewer"},
                "path": "pkg/a.go",
                "line": 12,
                "body": "Why is this needed?",
                "html_url": "https://example.test/root",
            },
            {
                "id": 11,
                "user": {"login": "Author"},
                "author_association": "CONTRIBUTOR",
                "body": "Updated the design.",
                "html_url": "https://example.test/reply",
                "in_reply_to_id": 10,
            },
            {
                "id": 12,
                "user": {"login": "Other"},
                "body": "Unrelated.",
            },
        ]

        result = HISTORY.collect_reviewer_comments(comments, "reviewer")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["line"], 12)
        self.assertEqual(result[0]["replies"][0]["author"], "Author")
        self.assertEqual(result[0]["replies"][0]["body"], "Updated the design.")

    def test_clipped_preserves_short_text_and_marks_long_text(self) -> None:
        self.assertEqual(HISTORY.clipped(" short ", 10), "short")
        self.assertEqual(HISTORY.clipped("abcdefghij", 8), "abcde...")
        self.assertEqual(HISTORY.clipped("abcdefghij", 0), "abcdefghij")


if __name__ == "__main__":
    unittest.main()
