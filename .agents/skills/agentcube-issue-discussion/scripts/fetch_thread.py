#!/usr/bin/env python3
"""Fetch AgentCube issue/PR discussion context as JSON."""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request


def request_page(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agentcube-issue-discussion-skill",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.headers
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"error": "not_found", "url": url}, {}
        raise


def request_json(url):
    data, _ = request_page(url)
    return data


def next_link(link_header):
    for part in link_header.split(","):
        if 'rel="next"' in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


def request_all_pages(url):
    items = []
    while url:
        data, headers = request_page(url)
        if not isinstance(data, list):
            return data
        items.extend(data)
        url = next_link(headers.get("Link", ""))
    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("number", type=int, help="GitHub issue or PR number")
    parser.add_argument("--repo", default="volcano-sh/agentcube", help="owner/repo")
    args = parser.parse_args()

    base = f"https://api.github.com/repos/{args.repo}"
    number = args.number

    issue = request_json(f"{base}/issues/{number}")
    comments = request_all_pages(f"{base}/issues/{number}/comments?per_page=100")

    result = {
        "repo": args.repo,
        "number": number,
        "issue": issue,
        "comments": comments,
    }

    if isinstance(issue, dict) and issue.get("pull_request"):
        result["pull_request"] = request_json(f"{base}/pulls/{number}")
        result["pull_files"] = request_all_pages(f"{base}/pulls/{number}/files?per_page=100")
        result["pull_commits"] = request_all_pages(f"{base}/pulls/{number}/commits?per_page=100")
        result["review_comments"] = request_all_pages(f"{base}/pulls/{number}/comments?per_page=100")

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
