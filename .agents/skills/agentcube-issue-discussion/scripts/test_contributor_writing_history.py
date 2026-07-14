#!/usr/bin/env python3

import argparse
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("contributor_writing_history.py")
SPEC = importlib.util.spec_from_file_location("contributor_writing_history", SCRIPT)
assert SPEC and SPEC.loader
HISTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HISTORY)


class ContributorWritingHistoryTest(unittest.TestCase):
    def test_metrics_remove_template_and_generated_blocks(self) -> None:
        body = """<!-- template -->
**What happened**:

Visible words here.
- [ ] task
```text
evidence
```
<!-- This is an auto-generated comment: summary -->
# Bot Summary
Generated words.
<!-- end of auto-generated comment: summary -->
"""

        metrics = HISTORY.markdown_metrics(body)

        self.assertEqual(metrics["headings"], ["What happened"])
        self.assertEqual(metrics["task_items"], 1)
        self.assertEqual(metrics["code_fences"], 1)
        self.assertNotIn("Generated", HISTORY.clean_visible_markdown(body))

    def test_first_external_response_excludes_author_bots_and_commands(self) -> None:
        entries = [
            {
                "user": {"login": "author", "type": "User"},
                "body": "More context",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "user": {"login": "prow-bot", "type": "Bot"},
                "body": "Automated result",
                "created_at": "2026-01-01T00:01:00Z",
            },
            {
                "user": {"login": "codecov-commenter", "type": "User"},
                "body": "Coverage report",
                "created_at": "2026-01-01T00:01:30Z",
            },
            {
                "user": {"login": "maintainer", "type": "User"},
                "body": "/lgtm",
                "created_at": "2026-01-01T00:02:00Z",
            },
            {
                "user": {"login": "maintainer", "type": "User"},
                "author_association": "MEMBER",
                "body": "Please clarify the compatibility contract.",
                "created_at": "2026-01-01T00:03:00Z",
                "html_url": "https://example.test/comment",
            },
        ]

        response = HISTORY.first_external_response(entries, "Author")

        self.assertIsNotNone(response)
        self.assertEqual(response["author"], "maintainer")
        self.assertIn("compatibility", response["body"])

    def test_parse_item_ref(self) -> None:
        self.assertEqual(HISTORY.parse_item_ref("owner/repo#431"), ("owner/repo", 431))
        with self.assertRaises(argparse.ArgumentTypeError):
            HISTORY.parse_item_ref("repo#431")

    def test_next_link(self) -> None:
        header = (
            '<https://api.example.test/items?page=2>; rel="next", '
            '<https://api.example.test/items?page=4>; rel="last"'
        )
        self.assertEqual(
            HISTORY.next_link(header), "https://api.example.test/items?page=2"
        )
        self.assertIsNone(HISTORY.next_link(""))


if __name__ == "__main__":
    unittest.main()
