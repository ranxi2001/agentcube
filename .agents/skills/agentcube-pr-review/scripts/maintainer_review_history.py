#!/usr/bin/env python3
"""Fetch a compact, evidence-oriented history for one GitHub reviewer."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from typing import Any


def request_json(url: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agentcube-pr-review-skill",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_login(value: str | None) -> str:
    return (value or "").casefold()


def comment_author(comment: dict[str, Any]) -> str:
    return str(comment.get("user", {}).get("login", ""))


def collect_reviewer_comments(
    comments: list[dict[str, Any]], reviewer: str
) -> list[dict[str, Any]]:
    reviewer_key = normalize_login(reviewer)
    reviewer_comments = [
        comment
        for comment in comments
        if normalize_login(comment_author(comment)) == reviewer_key
    ]
    replies_by_root: dict[int, list[dict[str, Any]]] = {}
    for comment in comments:
        root_id = comment.get("in_reply_to_id")
        if isinstance(root_id, int):
            replies_by_root.setdefault(root_id, []).append(comment)

    result: list[dict[str, Any]] = []
    for comment in reviewer_comments:
        comment_id = comment.get("id")
        replies = replies_by_root.get(comment_id, []) if isinstance(comment_id, int) else []
        result.append(
            {
                "id": comment_id,
                "path": comment.get("path"),
                "line": comment.get("line") or comment.get("original_line"),
                "created_at": comment.get("created_at"),
                "body": comment.get("body", ""),
                "url": comment.get("html_url"),
                "in_reply_to_id": comment.get("in_reply_to_id"),
                "replies": [
                    {
                        "id": reply.get("id"),
                        "author": comment_author(reply),
                        "association": reply.get("author_association"),
                        "created_at": reply.get("created_at"),
                        "body": reply.get("body", ""),
                        "url": reply.get("html_url"),
                    }
                    for reply in replies
                ],
            }
        )
    return result


def fetch_pr_review(repo: str, number: int, reviewer: str) -> dict[str, Any]:
    base = f"https://api.github.com/repos/{repo}"
    pr = request_json(f"{base}/pulls/{number}")
    files = request_json(f"{base}/pulls/{number}/files?per_page=100")
    reviews = request_json(f"{base}/pulls/{number}/reviews?per_page=100")
    review_comments = request_json(f"{base}/pulls/{number}/comments?per_page=100")
    issue_comments = request_json(f"{base}/issues/{number}/comments?per_page=100")
    reviewer_key = normalize_login(reviewer)

    author = pr.get("user", {}).get("login")
    return {
        "number": number,
        "title": pr.get("title"),
        "url": pr.get("html_url"),
        "state": pr.get("state"),
        "merged": pr.get("merged"),
        "draft": pr.get("draft"),
        "author": author,
        "reviewer_is_author": normalize_login(author) == reviewer_key,
        "created_at": pr.get("created_at"),
        "merged_at": pr.get("merged_at"),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
        "changed_files": pr.get("changed_files"),
        "files": [file.get("filename") for file in files],
        "review_summaries": [
            {
                "id": review.get("id"),
                "state": review.get("state"),
                "submitted_at": review.get("submitted_at"),
                "body": review.get("body", ""),
                "url": review.get("html_url"),
                "commit_id": review.get("commit_id"),
            }
            for review in reviews
            if normalize_login(review.get("user", {}).get("login")) == reviewer_key
            and (review.get("body", "").strip() or review.get("state") != "COMMENTED")
        ],
        "inline_comments": collect_reviewer_comments(review_comments, reviewer),
        "issue_comments": [
            {
                "id": comment.get("id"),
                "created_at": comment.get("created_at"),
                "body": comment.get("body", ""),
                "url": comment.get("html_url"),
            }
            for comment in issue_comments
            if normalize_login(comment_author(comment)) == reviewer_key
        ],
    }


def clipped(value: str, limit: int) -> str:
    text = value.strip()
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def render_markdown(records: list[dict[str, Any]], reviewer: str, body_limit: int) -> str:
    lines = [
        f"# Review History: @{reviewer}",
        "",
        "> Public GitHub evidence only. Review comments are observations, not automatic project consensus.",
        "",
    ]
    for record in records:
        outcome = "merged" if record["merged"] else record["state"]
        lines.extend(
            [
                f"## PR #{record['number']}: {record['title']}",
                "",
                f"- URL: {record['url']}",
                f"- Outcome: {outcome}",
                f"- Author: @{record['author']}",
                f"- Reviewer is author: {str(record['reviewer_is_author']).lower()}",
                (
                    "- Diff: "
                    f"{record['changed_files']} files, +{record['additions']}/-{record['deletions']}"
                ),
                "- Files: " + ", ".join(f"`{path}`" for path in record["files"]),
                "",
            ]
        )

        if record["reviewer_is_author"]:
            lines.extend(
                [
                    "> Exclude this PR when inferring review method; the selected user is the author.",
                    "",
                ]
            )

        for review in record["review_summaries"]:
            lines.extend(
                [
                    f"### Review {review['state']}",
                    "",
                    f"- Submitted: {review['submitted_at']}",
                    f"- URL: {review['url']}",
                ]
            )
            if review["body"].strip():
                lines.extend(["", clipped(review["body"], body_limit), ""])

        if record["inline_comments"]:
            lines.extend(["### Inline Comments", ""])
        for comment in record["inline_comments"]:
            location = f"{comment['path']}:{comment['line']}"
            lines.extend(
                [
                    f"- [{location}]({comment['url']})",
                    "",
                    clipped(comment["body"], body_limit),
                    "",
                ]
            )
            for reply in comment["replies"]:
                lines.extend(
                    [
                        f"  Reply by @{reply['author']} ({reply['association']}):",
                        "",
                        "  " + clipped(reply["body"], body_limit).replace("\n", "\n  "),
                        "",
                    ]
                )

        if record["issue_comments"]:
            lines.extend(["### Conversation Comments", ""])
        for comment in record["issue_comments"]:
            lines.extend(
                [
                    f"- [Comment]({comment['url']}), {comment['created_at']}",
                    "",
                    clipped(comment["body"], body_limit),
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prs", nargs="+", type=int, help="PR numbers to inspect")
    parser.add_argument("--repo", default="volcano-sh/agentcube", help="owner/repo")
    parser.add_argument("--reviewer", required=True, help="GitHub login")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument(
        "--exclude-authored",
        action="store_true",
        help="Drop PRs authored by the selected reviewer",
    )
    parser.add_argument(
        "--body-limit",
        type=int,
        default=1200,
        help="Maximum body characters in Markdown; 0 keeps full text",
    )
    args = parser.parse_args()

    records = [fetch_pr_review(args.repo, number, args.reviewer) for number in args.prs]
    if args.exclude_authored:
        records = [record for record in records if not record["reviewer_is_author"]]
    if args.format == "json":
        json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(records, args.reviewer, args.body_limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
