#!/usr/bin/env python3
"""Measure cage-bro sandbox latency through its E2B-compatible REST API."""

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_URL = "http://127.0.0.1:18090"
DEFAULT_COMMAND = "printf 'print(\"ok\")\\n' | python3"


def percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * pct))
    return round(ordered[index], 2)


def summarize(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {
            "count": 0,
            "mean_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "min_ms": None,
            "max_ms": None,
        }
    return {
        "count": len(values),
        "mean_ms": round(statistics.mean(values), 2),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "min_ms": round(min(values), 2),
        "max_ms": round(max(values), 2),
    }


def request_json(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 20.0,
) -> Tuple[int, Dict[str, Any]]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return resp.status, {}
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = {"raw": raw}
        return exc.code, body


def run_once(index: int, args: argparse.Namespace) -> Dict[str, Any]:
    sandbox_id = None
    try:
        t0 = time.perf_counter()
        status, body = request_json(
            "POST",
            args.url.rstrip("/") + "/sandboxes",
            {
                "templateID": args.template_id,
                "memoryMB": args.memory_mb,
            },
            timeout=args.timeout,
        )
        create_ms = (time.perf_counter() - t0) * 1000
        if status not in (200, 201):
            raise RuntimeError("create failed: status=%s body=%s" % (status, body))
        sandbox_id = body["sandboxID"]

        t1 = time.perf_counter()
        status, exec_body = request_json(
            "POST",
            args.url.rstrip("/") + "/sandboxes/%s/exec" % sandbox_id,
            {
                "command": args.command,
                "timeoutMs": int(args.timeout * 1000),
            },
            timeout=args.timeout,
        )
        run_ms = (time.perf_counter() - t1) * 1000
        if status != 200:
            raise RuntimeError("exec failed: status=%s body=%s" % (status, exec_body))

        t2 = time.perf_counter()
        status, delete_body = request_json(
            "DELETE",
            args.url.rstrip("/") + "/sandboxes/%s" % sandbox_id,
            timeout=args.timeout,
        )
        delete_ms = (time.perf_counter() - t2) * 1000
        if status not in (200, 204):
            raise RuntimeError("delete failed: status=%s body=%s" % (status, delete_body))

        stdout = exec_body.get("stdout", "")
        return {
            "index": index,
            "sandbox_id_prefix": sandbox_id[:8],
            "create_session_ms": round(create_ms, 2),
            "run_code_ms": round(run_ms, 2),
            "reported_exec_duration_ms": exec_body.get("durationMs"),
            "delete_session_ms": round(delete_ms, 2),
            "total_ms": round(create_ms + run_ms + delete_ms, 2),
            "output": stdout.strip(),
            "exit_code": exec_body.get("exitCode"),
            "success": stdout.strip() == args.expected_output and exec_body.get("exitCode") == 0,
        }
    except Exception as exc:
        return {
            "index": index,
            "sandbox_id_prefix": sandbox_id[:8] if sandbox_id else None,
            "error": repr(exc),
            "success": False,
        }
    finally:
        if sandbox_id:
            try:
                request_json(
                    "DELETE",
                    args.url.rstrip("/") + "/sandboxes/%s" % sandbox_id,
                    timeout=args.timeout,
                )
            except Exception:
                pass


def run_sequential(args: argparse.Namespace) -> List[Dict[str, Any]]:
    return [run_once(index, args) for index in range(args.count)]


def run_concurrent(args: argparse.Namespace) -> List[Dict[str, Any]]:
    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(run_once, index, args) for index in range(args.count)]
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda item: item["index"])


def summarize_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    successful = [item for item in results if item.get("success")]
    failed = [item for item in results if not item.get("success")]
    return {
        "case_count": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "create_session": summarize([item["create_session_ms"] for item in successful]),
        "run_code": summarize([item["run_code_ms"] for item in successful]),
        "reported_exec_duration": summarize(
            [float(item["reported_exec_duration_ms"]) for item in successful]
        ),
        "delete_session": summarize([item["delete_session_ms"] for item in successful]),
        "total_latency": summarize([item["total_ms"] for item in successful]),
        "errors": [item for item in failed if item.get("error")],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--mode", choices=["sequential", "concurrent"], default="sequential")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--template-id", default="base")
    parser.add_argument("--memory-mb", type=int, default=512)
    parser.add_argument("--command", default=DEFAULT_COMMAND)
    parser.add_argument("--expected-output", default="ok")
    parser.add_argument("--output", default=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    t0 = time.perf_counter()
    if args.mode == "sequential":
        results = run_sequential(args)
    else:
        results = run_concurrent(args)
    wall_clock_ms = (time.perf_counter() - t0) * 1000

    payload = {
        "run_started_at": datetime.utcnow().isoformat() + "Z",
        "mode": args.mode,
        "count": args.count,
        "concurrency": args.concurrency if args.mode == "concurrent" else 1,
        "url": args.url,
        "template_id": args.template_id,
        "memory_mb": args.memory_mb,
        "command": args.command,
        "wall_clock_ms": round(wall_clock_ms, 2),
        "summary": summarize_results(results),
        "results": results,
    }

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(rendered + "\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
