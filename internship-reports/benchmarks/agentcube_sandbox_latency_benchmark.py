#!/usr/bin/env python3
"""Measure AgentCube CodeInterpreter sandbox latency.

This benchmark intentionally avoids LLM calls. It measures the infrastructure
path only: create session, run a tiny Python snippet, and delete session.
"""

import argparse
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentcube import CodeInterpreterClient


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = REPO_ROOT / "cmd/cli/examples/math-agent/.env"
DEFAULT_CODE = "print('ok')"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


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


def run_once(index: int, args: argparse.Namespace) -> Dict[str, Any]:
    client = None
    try:
        t0 = time.perf_counter()
        client = CodeInterpreterClient(
            name=args.interpreter_name,
            namespace=args.namespace,
            ttl=args.ttl,
            verbose=False,
        )
        create_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        output = client.run_code("python", args.code, timeout=args.timeout).strip()
        run_ms = (time.perf_counter() - t1) * 1000

        session_id = client.session_id
        t2 = time.perf_counter()
        client.stop()
        client = None
        delete_ms = (time.perf_counter() - t2) * 1000

        return {
            "index": index,
            "session_id_prefix": session_id[:8] if session_id else None,
            "create_session_ms": round(create_ms, 2),
            "run_code_ms": round(run_ms, 2),
            "delete_session_ms": round(delete_ms, 2),
            "total_ms": round(create_ms + run_ms + delete_ms, 2),
            "output": output,
            "success": output == args.expected_output,
        }
    except Exception as exc:
        return {
            "index": index,
            "error": repr(exc),
            "success": False,
        }
    finally:
        if client is not None:
            client.stop()


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
        "delete_session": summarize([item["delete_session_ms"] for item in successful]),
        "total_latency": summarize([item["total_ms"] for item in successful]),
        "errors": [item for item in failed if item.get("error")],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--mode", choices=["sequential", "concurrent"], default="sequential")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--interpreter-name", default="my-interpreter")
    parser.add_argument("--ttl", type=int, default=600)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--code", default=DEFAULT_CODE)
    parser.add_argument("--expected-output", default="ok")
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    load_env_file(args.env_file)

    missing = [
        name for name in ("WORKLOAD_MANAGER_URL", "ROUTER_URL")
        if not os.environ.get(name)
    ]
    if missing:
        parser.error("missing required environment variables: " + ", ".join(missing))

    t0 = time.perf_counter()
    if args.mode == "sequential":
        results = run_sequential(args)
    else:
        results = run_concurrent(args)
    wall_clock_ms = (time.perf_counter() - t0) * 1000

    payload = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "count": args.count,
        "concurrency": args.concurrency if args.mode == "concurrent" else 1,
        "namespace": args.namespace,
        "interpreter_name": args.interpreter_name,
        "workload_manager_url": os.environ.get("WORKLOAD_MANAGER_URL"),
        "router_url": os.environ.get("ROUTER_URL"),
        "wall_clock_ms": round(wall_clock_ms, 2),
        "summary": summarize_results(results),
        "results": results,
    }

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
