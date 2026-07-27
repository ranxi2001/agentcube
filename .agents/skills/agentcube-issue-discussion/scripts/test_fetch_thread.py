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


SCRIPT = Path(__file__).with_name("fetch_thread.py")
SPEC = importlib.util.spec_from_file_location("fetch_thread", SCRIPT)
assert SPEC and SPEC.loader
FETCH_THREAD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FETCH_THREAD)


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


class FetchThreadTest(unittest.TestCase):
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
                FETCH_THREAD.urllib.request, "urlopen", side_effect=responses
            ) as urlopen:
                result = FETCH_THREAD.request_all_pages(first_url)

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
                request.get_header("User-agent"),
                "agentcube-issue-discussion-skill",
            )
            self.assertEqual(call.kwargs["timeout"], 30)

    def test_request_json_and_pagination_preserve_404_result(self):
        url = "https://api.example.test/missing"

        for requester in (FETCH_THREAD.request_json, FETCH_THREAD.request_all_pages):
            error = urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            with self.subTest(requester=requester.__name__):
                with mock.patch.object(
                    FETCH_THREAD.urllib.request, "urlopen", side_effect=error
                ):
                    self.assertEqual(
                        requester(url), {"error": "not_found", "url": url}
                    )

    def test_main_preserves_full_pr_arrays(self):
        comments = [{"id": index} for index in range(101)]
        files = [{"filename": f"file-{index}"} for index in range(102)]
        commits = [{"sha": str(index)} for index in range(103)]
        reviews = [{"id": index} for index in range(104)]
        output = io.StringIO()

        with mock.patch.object(
            FETCH_THREAD,
            "request_json",
            side_effect=[
                {"title": "Example", "pull_request": {"url": "pull"}},
                {"state": "open"},
            ],
        ):
            with mock.patch.object(
                FETCH_THREAD,
                "request_all_pages",
                side_effect=[comments, files, commits, reviews],
            ):
                with mock.patch.object(sys, "argv", [str(SCRIPT), "442"]):
                    with mock.patch.object(sys, "stdout", output):
                        self.assertEqual(FETCH_THREAD.main(), 0)

        result = json.loads(output.getvalue())
        self.assertEqual(result["comments"], comments)
        self.assertEqual(result["pull_files"], files)
        self.assertEqual(result["pull_commits"], commits)
        self.assertEqual(result["review_comments"], reviews)


if __name__ == "__main__":
    unittest.main()
