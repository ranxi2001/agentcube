#!/usr/bin/env python3
"""Fetch AgentCube PR status and review surface."""

import argparse
import json
import os
import re
import sys
import urllib.request


def request_page(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agentcube-pr-management-skill",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.headers


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
    parser.add_argument("number", type=int, help="GitHub PR number")
    parser.add_argument("--repo", default="volcano-sh/agentcube", help="owner/repo")
    parser.add_argument(
        "--review-comment-limit",
        type=int,
        default=20,
        help="Number of newest review comments to include; use 0 for all",
    )
    args = parser.parse_args()
    if args.review_comment_limit < 0:
        parser.error("--review-comment-limit must be non-negative")

    base = f"https://api.github.com/repos/{args.repo}"
    pr = request_json(f"{base}/pulls/{args.number}")
    files = request_all_pages(f"{base}/pulls/{args.number}/files?per_page=100")
    commits = request_all_pages(f"{base}/pulls/{args.number}/commits?per_page=100")
    issue_comments = request_all_pages(f"{base}/issues/{args.number}/comments?per_page=100")
    review_comments = request_all_pages(f"{base}/pulls/{args.number}/comments?per_page=100")
    ordered_review_comments = (
        sorted(
            (item for item in review_comments if isinstance(item, dict)),
            key=lambda item: item.get("created_at") or "",
        )
        if isinstance(review_comments, list)
        else review_comments
    )
    review_comment_preview = (
        ordered_review_comments
        if not isinstance(ordered_review_comments, list) or args.review_comment_limit == 0
        else ordered_review_comments[-args.review_comment_limit :]
    )

    result = {
        "number": args.number,
        "title": pr.get("title") if isinstance(pr, dict) else None,
        "state": pr.get("state") if isinstance(pr, dict) else None,
        "merged": pr.get("merged") if isinstance(pr, dict) else None,
        "labels": [label["name"] for label in pr.get("labels", [])] if isinstance(pr, dict) else [],
        "draft": pr.get("draft") if isinstance(pr, dict) else None,
        "changed_files": pr.get("changed_files") if isinstance(pr, dict) else None,
        "additions": pr.get("additions") if isinstance(pr, dict) else None,
        "deletions": pr.get("deletions") if isinstance(pr, dict) else None,
        "updated_at": pr.get("updated_at") if isinstance(pr, dict) else None,
        "base_sha": pr.get("base", {}).get("sha") if isinstance(pr, dict) else None,
        "head_sha": pr.get("head", {}).get("sha") if isinstance(pr, dict) else None,
        "mergeable_state": pr.get("mergeable_state") if isinstance(pr, dict) else None,
        "files": [
            {
                "filename": f.get("filename"),
                "status": f.get("status"),
                "additions": f.get("additions"),
                "deletions": f.get("deletions"),
            }
            for f in files
            if isinstance(f, dict)
        ]
        if isinstance(files, list)
        else files,
        "commits": [
            {
                "sha": c.get("sha", "")[:7],
                "message": c.get("commit", {}).get("message", "").split("\n")[0],
            }
            for c in commits
            if isinstance(c, dict)
        ]
        if isinstance(commits, list)
        else commits,
        "issue_comments_count": len(issue_comments) if isinstance(issue_comments, list) else None,
        "review_comments_count": len(review_comments) if isinstance(review_comments, list) else None,
        "review_comments": [
            {
                "user": c.get("user", {}).get("login"),
                "id": c.get("id"),
                "created_at": c.get("created_at"),
                "path": c.get("path"),
                "line": c.get("line") or c.get("original_line"),
                "commit_id": c.get("commit_id"),
                "original_commit_id": c.get("original_commit_id"),
                "pull_request_review_id": c.get("pull_request_review_id"),
                "in_reply_to_id": c.get("in_reply_to_id"),
                "html_url": c.get("html_url"),
                "body": c.get("body", "")[:500],
            }
            for c in review_comment_preview
            if isinstance(c, dict)
        ]
        if isinstance(review_comment_preview, list)
        else review_comment_preview,
    }

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
