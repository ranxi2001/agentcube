#!/usr/bin/env python3
"""Fetch compact public evidence for a contributor's issue and PR writing."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from typing import Any


AUTO_GENERATED_BLOCK = re.compile(
    r"<!--\s*This is an auto-generated comment.*?"
    r"<!--\s*end of auto-generated comment.*?-->",
    flags=re.IGNORECASE | re.DOTALL,
)
HTML_COMMENT = re.compile(r"<!--.*?-->", flags=re.DOTALL)
ITEM_REF = re.compile(r"^(?P<repo>[^/\s]+/[^#\s]+)#(?P<number>[1-9]\d*)$")
AUTOMATION_LOGIN = re.compile(
    r"(?:\[bot\]|-bot$|bot$|robot$|^codecov|^gemini|^copilot|coderabbit|github-actions)",
    flags=re.IGNORECASE,
)


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agentcube-contributor-writing-history",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def request_page(url: str) -> tuple[Any, dict[str, str]]:
    request = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
        return data, dict(response.headers.items())


def request_json(url: str) -> Any:
    data, _ = request_page(url)
    return data


def next_link(link_header: str) -> str | None:
    for part in link_header.split(","):
        if 'rel="next"' in part:
            match = re.search(r"<([^>]+)>", part)
            return match.group(1) if match else None
    return None


def request_all_pages(url: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    while url:
        data, headers = request_page(url)
        if not isinstance(data, list):
            raise TypeError(f"expected a list response from {url}")
        items.extend(data)
        url = next_link(headers.get("Link", "")) or ""
    return items


def parse_item_ref(value: str) -> tuple[str, int]:
    match = ITEM_REF.fullmatch(value)
    if not match:
        raise argparse.ArgumentTypeError("expected owner/repo#number")
    return match.group("repo"), int(match.group("number"))


def clean_visible_markdown(body: str | None) -> str:
    text = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    text = AUTO_GENERATED_BLOCK.sub("", text)
    return HTML_COMMENT.sub("", text).strip()


def markdown_metrics(body: str | None) -> dict[str, Any]:
    visible = clean_visible_markdown(body)
    lines = visible.splitlines()
    headings = []
    for line in lines:
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if not match:
            match = re.match(r"^\*\*(.+?)\*\*:?\s*$", line)
        if match:
            headings.append(match.group(1).strip())
    task_items = [line for line in lines if re.match(r"^\s*[-*]\s+\[[ xX]\]\s+", line)]
    links = re.findall(r"\[[^\]]+\]\([^)]+\)|https?://\S+", visible)
    return {
        "visible_words": len(re.findall(r"\S+", visible)),
        "nonblank_lines": sum(bool(line.strip()) for line in lines),
        "headings": headings,
        "task_items": len(task_items),
        "links": len(links),
        "code_fences": visible.count("```") // 2,
    }


def login(item: dict[str, Any]) -> str:
    user = item.get("user") or {}
    return str(user.get("login") or "")


def is_bot(item: dict[str, Any]) -> bool:
    user = item.get("user") or {}
    name = str(user.get("login") or "").casefold()
    return user.get("type") == "Bot" or bool(AUTOMATION_LOGIN.search(name))


def is_command_only(body: str | None) -> bool:
    lines = [line.strip() for line in (body or "").splitlines() if line.strip()]
    return bool(lines) and all(line.startswith("/") and " " not in line for line in lines)


def first_external_response(
    entries: list[dict[str, Any]], author: str
) -> dict[str, Any] | None:
    author_key = author.casefold()
    candidates = []
    for entry in entries:
        body = str(entry.get("body") or "").strip()
        if (
            not body
            or login(entry).casefold() == author_key
            or is_bot(entry)
            or is_command_only(body)
        ):
            continue
        candidates.append(entry)
    if not candidates:
        return None
    response = min(
        candidates,
        key=lambda item: str(item.get("created_at") or item.get("submitted_at") or ""),
    )
    return {
        "author": login(response),
        "association": response.get("author_association"),
        "created_at": response.get("created_at") or response.get("submitted_at"),
        "body": response.get("body") or "",
        "url": response.get("html_url"),
    }


def fetch_record(repo: str, number: int, expected_author: str) -> dict[str, Any]:
    base = f"https://api.github.com/repos/{repo}"
    issue = request_json(f"{base}/issues/{number}")
    comments = request_all_pages(f"{base}/issues/{number}/comments?per_page=100")
    is_pr = bool(issue.get("pull_request"))
    pull = request_json(f"{base}/pulls/{number}") if is_pr else None
    reviews = request_all_pages(f"{base}/pulls/{number}/reviews?per_page=100") if is_pr else []
    review_comments = (
        request_all_pages(f"{base}/pulls/{number}/comments?per_page=100") if is_pr else []
    )
    body = issue.get("body") or ""
    actual_author = login(issue)
    response_entries = list(comments) + list(reviews) + list(review_comments)
    response = first_external_response(response_entries, actual_author)

    return {
        "repo": repo,
        "number": number,
        "type": "pr" if is_pr else "issue",
        "title": issue.get("title"),
        "url": issue.get("html_url"),
        "author": actual_author,
        "author_matches": actual_author.casefold() == expected_author.casefold(),
        "state": issue.get("state"),
        "state_reason": issue.get("state_reason"),
        "created_at": issue.get("created_at"),
        "closed_at": issue.get("closed_at"),
        "merged": pull.get("merged") if pull else None,
        "merged_at": pull.get("merged_at") if pull else None,
        "changed_files": pull.get("changed_files") if pull else None,
        "additions": pull.get("additions") if pull else None,
        "deletions": pull.get("deletions") if pull else None,
        "labels": [label.get("name") for label in issue.get("labels", [])],
        "metrics": markdown_metrics(body),
        "body": clean_visible_markdown(body),
        "first_external_response": response,
    }


def clipped(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def render_markdown(records: list[dict[str, Any]], author: str, body_limit: int) -> str:
    lines = [
        f"# Public Writing History: @{author}",
        "",
        (
            "> Bodies can contain repository template text. Infer reusable patterns only "
            "after comparing multiple artifact types and repositories."
        ),
        "",
    ]
    for record in records:
        metrics = record["metrics"]
        outcome = "merged" if record["merged"] else record["state"]
        lines.extend(
            [
                f"## {record['repo']}#{record['number']}: {record['title']}",
                "",
                f"- Type/outcome: {record['type']} / {outcome}",
                f"- URL: {record['url']}",
                f"- Author match: {str(record['author_matches']).lower()}",
                (
                    "- Body metrics: "
                    f"{metrics['visible_words']} words, "
                    f"{metrics['nonblank_lines']} nonblank lines, "
                    f"{metrics['task_items']} tasks, {metrics['links']} links, "
                    f"{metrics['code_fences']} code blocks"
                ),
                "- Headings: " + (" | ".join(metrics["headings"]) or "none"),
            ]
        )
        if record["type"] == "pr":
            lines.append(
                f"- Diff: {record['changed_files']} files, "
                f"+{record['additions']}/-{record['deletions']}"
            )
        lines.extend(["", "### Body", "", clipped(record["body"], body_limit) or "-"])
        response = record["first_external_response"]
        lines.extend(["", "### First External Human Response", ""])
        if response:
            lines.extend(
                [
                    f"- @{response['author']} ({response['association']}), "
                    f"{response['created_at']}",
                    f"- {response['url']}",
                    "",
                    clipped(response["body"], body_limit),
                ]
            )
        else:
            lines.append("- none found")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("items", nargs="+", type=parse_item_ref, help="owner/repo#number")
    parser.add_argument("--author", required=True, help="Expected GitHub login")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument(
        "--body-limit",
        type=int,
        default=1600,
        help="Markdown clip length; 0 keeps full text",
    )
    args = parser.parse_args()

    records = [fetch_record(repo, number, args.author) for repo, number in args.items]
    mismatches = [record["url"] for record in records if not record["author_matches"]]
    if mismatches:
        print("warning: expected author does not match: " + ", ".join(mismatches), file=sys.stderr)
    if args.format == "json":
        json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(records, args.author, args.body_limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
