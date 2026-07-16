#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import call, patch


SCRIPT = Path(__file__).with_name("maintainer_review_history.py")
SPEC = importlib.util.spec_from_file_location("maintainer_review_history", SCRIPT)
assert SPEC and SPEC.loader
HISTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HISTORY)


class MaintainerReviewHistoryTest(unittest.TestCase):
    def test_request_json_pages_fetches_every_page_in_order(self) -> None:
        first_page = [{"id": item} for item in range(100)]
        second_page = [{"id": 100}, {"id": 101}]

        with patch.object(
            HISTORY, "request_json", side_effect=[first_page, second_page]
        ) as request:
            result = HISTORY.request_json_pages(
                "https://api.example.test/comments?per_page=50"
            )

        self.assertEqual([item["id"] for item in result], list(range(102)))
        self.assertEqual(
            request.call_args_list,
            [
                call("https://api.example.test/comments?per_page=100&page=1"),
                call("https://api.example.test/comments?per_page=100&page=2"),
            ],
        )

    def test_fetch_pr_review_paginates_every_list_endpoint(self) -> None:
        pr = {
            "title": "Test PR",
            "html_url": "https://example.test/pull/7",
            "state": "open",
            "merged": False,
            "draft": False,
            "user": {"login": "Author"},
            "created_at": "2026-01-01T00:00:00Z",
            "merged_at": None,
            "additions": 1,
            "deletions": 0,
            "changed_files": 1,
        }
        paginated_results = [
            [{"filename": "pkg/a.go"}],
            [
                {
                    "id": 1,
                    "user": {"login": "Reviewer"},
                    "state": "APPROVED",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "body": "LGTM",
                    "html_url": "https://example.test/review/1",
                    "commit_id": "abc",
                }
            ],
            [
                {
                    "id": 2,
                    "user": {"login": "Reviewer"},
                    "path": "pkg/a.go",
                    "line": 1,
                    "body": "Question",
                    "html_url": "https://example.test/inline/2",
                }
            ],
            [
                {
                    "id": 3,
                    "user": {"login": "Reviewer"},
                    "body": "Follow-up",
                    "html_url": "https://example.test/comment/3",
                }
            ],
        ]

        with (
            patch.object(HISTORY, "request_json", return_value=pr),
            patch.object(
                HISTORY, "request_json_pages", side_effect=paginated_results
            ) as request_pages,
        ):
            result = HISTORY.fetch_pr_review("owner/repo", 7, "reviewer")

        base = "https://api.github.com/repos/owner/repo"
        self.assertEqual(
            request_pages.call_args_list,
            [
                call(f"{base}/pulls/7/files"),
                call(f"{base}/pulls/7/reviews"),
                call(f"{base}/pulls/7/comments"),
                call(f"{base}/issues/7/comments"),
            ],
        )
        self.assertEqual(result["files"], ["pkg/a.go"])
        self.assertEqual(result["review_summaries"][0]["state"], "APPROVED")
        self.assertEqual(result["inline_comments"][0]["id"], 2)
        self.assertEqual(result["issue_comments"][0]["id"], 3)

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
