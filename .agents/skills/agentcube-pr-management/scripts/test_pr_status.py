#!/usr/bin/env python3

import importlib.util
import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("pr_status.py")
SPEC = importlib.util.spec_from_file_location("pr_status", SCRIPT)
assert SPEC and SPEC.loader
PR_STATUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PR_STATUS)


class FakeResponse:
    def __init__(self, data, headers=None):
        self._body = json.dumps(data).encode("utf-8")
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class PRStatusTest(unittest.TestCase):
    def test_request_all_pages_follows_link_and_preserves_headers(self):
        first_url = "https://api.example.test/items?per_page=100"
        second_url = "https://api.example.test/items?per_page=100&page=2"
        responses = [
            FakeResponse(
                [{"id": 1}],
                {
                    "Link": (
                        f'<{second_url}>; rel="next", '
                        f'<{second_url}>; rel="last"'
                    )
                },
            ),
            FakeResponse([{"id": 2}]),
        ]

        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}, clear=True):
            with mock.patch.object(
                PR_STATUS.urllib.request, "urlopen", side_effect=responses
            ) as urlopen:
                result = PR_STATUS.request_all_pages(first_url)

        self.assertEqual(result, [{"id": 1}, {"id": 2}])
        self.assertEqual(
            [call.args[0].full_url for call in urlopen.call_args_list],
            [first_url, second_url],
        )
        for call in urlopen.call_args_list:
            request = call.args[0]
            self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
            self.assertEqual(
                request.get_header("User-agent"), "agentcube-pr-management-skill"
            )
            self.assertEqual(call.kwargs["timeout"], 30)

    def test_request_json_still_propagates_404(self):
        url = "https://api.example.test/missing"
        error = urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        with mock.patch.object(PR_STATUS.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                PR_STATUS.request_json(url)

        self.assertEqual(raised.exception.code, 404)

    def test_main_counts_all_comments_and_keeps_preview_shape(self):
        review_comments = [
            {
                "id": index,
                "user": {"login": f"reviewer-{index}"},
                "path": "pkg/example.go",
                "line": index + 1,
                "created_at": f"2026-07-31T{index // 60:02d}:{index % 60:02d}:00Z",
                "commit_id": "current-head",
                "original_commit_id": f"original-{index}",
                "pull_request_review_id": 1000 + index,
                "in_reply_to_id": None,
                "html_url": f"https://example.test/comments/{index}",
                "body": f"comment {index}",
            }
            for index in range(101)
        ]
        output = io.StringIO()

        with mock.patch.object(
            PR_STATUS,
            "request_json",
            return_value={
                "title": "Example",
                "state": "open",
                "merged": False,
                "labels": [],
            },
        ):
            with mock.patch.object(
                PR_STATUS,
                "request_all_pages",
                side_effect=[
                    [{"filename": "pkg/example.go", "status": "modified"}],
                    [{"sha": "123456789", "commit": {"message": "subject\nbody"}}],
                    [{"id": index} for index in range(102)],
                    list(reversed(review_comments)),
                ],
            ):
                with mock.patch.object(sys, "argv", [str(SCRIPT), "442"]):
                    with mock.patch.object(sys, "stdout", output):
                        self.assertEqual(PR_STATUS.main(), 0)

        result = json.loads(output.getvalue())
        self.assertEqual(result["issue_comments_count"], 102)
        self.assertEqual(result["review_comments_count"], 101)
        self.assertEqual(len(result["review_comments"]), 20)
        self.assertEqual(result["review_comments"][0]["user"], "reviewer-81")
        self.assertEqual(result["review_comments"][-1]["original_commit_id"], "original-100")
        self.assertEqual(result["review_comments"][-1]["pull_request_review_id"], 1100)
        self.assertEqual(result["commits"], [{"sha": "1234567", "message": "subject"}])


if __name__ == "__main__":
    unittest.main()
