#!/usr/bin/env python3
"""Run Gaokao math benchmark cases through direct LLM and AgentCube paths.

Default mode is a dry-run parser check. It does not call any LLM or sandbox unless
explicit methods are requested with --methods.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = Path(__file__).with_name("gaokao_math_2026_cases.json")
DEFAULT_ENV_FILE = REPO_ROOT / "cmd/cli/examples/math-agent/.env"


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs without printing secrets or requiring python-dotenv."""
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


def load_manifest(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest["_path"] = str(path.resolve())
    return manifest


def parse_markdown_questions(path: Path) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^###\s+(\d+)\.(?:.*)?$", text, flags=re.MULTILINE))
    section_starts = [m.start() for m in re.finditer(r"^##\s+", text, flags=re.MULTILINE)]
    questions = {}  # type: Dict[str, str]

    for index, match in enumerate(matches):
        number = match.group(1)
        start = match.start()
        next_question = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        next_sections = [pos for pos in section_starts if pos > start]
        next_section = min(next_sections) if next_sections else len(text)
        end = min(next_question, next_section)
        section = text[start:end].strip()
        questions[number] = section

    return questions


def resolve_questions_path(manifest: Dict[str, Any], manifest_path: Path) -> Path:
    configured = Path(manifest["questions_md"])
    if configured.is_absolute():
        return configured
    return (manifest_path.parent / configured).resolve()


def load_cases(
    manifest_path: Path,
    questions_override: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    manifest = load_manifest(manifest_path)
    questions_path = questions_override or resolve_questions_path(manifest, manifest_path)
    questions = parse_markdown_questions(questions_path)

    cases = []  # type: List[Dict[str, Any]]
    for raw_case in manifest["cases"]:
        case = dict(raw_case)
        question_no = str(case["question_no"])
        prompt = questions.get(question_no)
        if prompt is None:
            raise ValueError(f"question {question_no} not found in {questions_path}")
        case["prompt"] = prompt
        case["paper"] = manifest.get("paper")
        case["dataset_id"] = manifest.get("dataset_id")
        case["questions_md"] = str(questions_path)
        cases.append(case)

    return cases


def parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def select_cases(
    cases: List[Dict[str, Any]],
    requested_cases: List[str],
    requested_types: List[str],
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    selected = cases

    if requested_cases:
        wanted = set()
        for item in requested_cases:
            wanted.add(item)
            wanted.add(item.lower())
            if item.isdigit():
                wanted.add(str(int(item)))
                wanted.add(f"q{int(item):02d}")
                wanted.add(f"2026-gaokao-math-q{int(item):02d}")

        selected = [
            case for case in selected
            if case["id"] in wanted
            or case["id"].lower() in wanted
            or str(case["question_no"]) in wanted
            or f"q{int(case['question_no']):02d}" in wanted
        ]

    if requested_types:
        wanted_types = set(requested_types)
        selected = [case for case in selected if case.get("type") in wanted_types]

    if limit is not None:
        selected = selected[:limit]

    return selected


def build_prompt(case: Dict[str, Any], prefer_tool: bool = False) -> str:
    tool_hint = ""
    if prefer_tool:
        tool_hint = (
            "\n\n如果计算、枚举、数值验证或代数检验有帮助，请调用 Python 工具。"
            "工具中优先使用标准库，最终仍需根据工具结果给出数学答案。"
        )

    answer_style = {
        "single_choice": "请先给出最终选项字母，再给出极简理由。",
        "multiple_choice": "请先给出全部正确选项字母，顺序按 A/B/C/D，再给出极简理由。",
        "fill_blank": "请先给出每个空的最终值，再给出极简理由。",
        "solution": "请给出关键步骤和最终结论。",
        "proof_or_solution": "请给出关键证明步骤和最终结论。",
    }.get(case.get("type"), "请给出最终答案和必要步骤。")

    return (
        f"你正在解一道高考数学题。\n"
        f"题号：{case['question_no']}\n"
        f"题型：{case.get('type')}\n"
        f"要求：{answer_style}\n"
        f"最终结论请以“最终答案：”开头。\n\n"
        f"{case['prompt']}"
        f"{tool_hint}"
    )


def make_llm(max_tokens: int, temperature: float):
    from langchain_openai import ChatOpenAI

    missing = [
        name for name in ("OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_MODEL")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(
            "missing required environment variables: "
            + ", ".join(missing)
            + f". Put them in {DEFAULT_ENV_FILE} or export them before running."
        )

    return ChatOpenAI(
        model=os.environ["OPENAI_MODEL"],
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_API_BASE"],
        temperature=temperature,
        max_tokens=max_tokens,
    )


def normalize_math_text(text: str) -> str:
    normalized = text.lower()
    replacements = {
        "\\dfrac": "\\frac",
        "\\left": "",
        "\\right": "",
        "\\,": "",
        "\\ ": "",
        " ": "",
        "\n": "",
        "\t": "",
        "$": "",
        "π": "pi",
        "，": ",",
        "。": ".",
        "（": "(",
        "）": ")",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized


def aliases_for(grading: Dict[str, Any], expected: str) -> List[str]:
    aliases = grading.get("aliases", {}).get(expected)
    if aliases:
        return [expected, *aliases]
    return [expected]


def contains_math_alias(text: str, aliases: List[str]) -> Tuple[bool, Optional[str]]:
    normalized_text = normalize_math_text(text)
    for alias in aliases:
        normalized_alias = normalize_math_text(alias)
        if normalized_alias and normalized_alias in normalized_text:
            return True, alias
    return False, None


def extract_choice_letters(text: str) -> List[str]:
    upper = text.upper()
    explicit_patterns = [
        r"(?:最终答案|答案|答|选择|选项|选|ANSWER|OPTION)\s*[:：为是]?\s*([ABCD](?:\s*[,，、和与/]\s*[ABCD])*)",
        r"\b([ABCD](?:\s*[,，、和与/]\s*[ABCD])*)\b\s*(?:正确|为正确选项)",
    ]

    matches = []  # type: List[str]
    for pattern in explicit_patterns:
        matches.extend(re.findall(pattern, upper))

    if not matches:
        stripped = re.sub(r"[^ABCD]", "", upper.strip())
        if 1 <= len(stripped) <= 4:
            matches.append(stripped)

    if not matches:
        return []

    letters = re.findall(r"[ABCD]", matches[-1])
    deduped = []  # type: List[str]
    for letter in letters:
        if letter not in deduped:
            deduped.append(letter)
    return deduped


def grade_response(case: Dict[str, Any], response: str) -> Dict[str, Any]:
    grading = case.get("grading", {})
    mode = grading.get("mode", "manual")

    if mode == "choice":
        expected = grading["answer"]
        letters = extract_choice_letters(response)
        actual = letters[0] if letters else None
        return {
            "mode": mode,
            "accurate": actual == expected,
            "actual": actual,
            "expected": expected,
        }

    if mode == "choice_set":
        expected = sorted(grading["answer"])
        actual = sorted(extract_choice_letters(response))
        return {
            "mode": mode,
            "accurate": actual == expected,
            "actual": actual,
            "expected": expected,
        }

    if mode == "math_contains":
        matched = []  # type: List[str]
        for expected in grading["answers"]:
            ok, alias = contains_math_alias(response, aliases_for(grading, expected))
            if ok and alias is not None:
                matched.append(alias)
        return {
            "mode": mode,
            "accurate": bool(matched),
            "matched": matched,
            "expected": grading["answers"],
        }

    if mode == "math_all_contains":
        matched = {}  # type: Dict[str, str]
        for expected in grading["answers"]:
            ok, alias = contains_math_alias(response, aliases_for(grading, expected))
            if ok and alias is not None:
                matched[expected] = alias
        return {
            "mode": mode,
            "accurate": len(matched) == len(grading["answers"]),
            "matched": matched,
            "expected": grading["answers"],
        }

    return {
        "mode": mode,
        "accurate": None,
        "expected_summary": grading.get("expected_summary"),
    }


def usage_metadata(message: Any) -> Optional[Dict[str, Any]]:
    data = getattr(message, "usage_metadata", None)
    if data:
        return dict(data)
    response_metadata = getattr(message, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage")
    return dict(token_usage) if token_usage else None


def run_dry_case(case: Dict[str, Any]) -> Dict[str, Any]:
    grading = case.get("grading", {})
    return {
        "case_id": case["id"],
        "question_no": case["question_no"],
        "type": case.get("type"),
        "method": "dry_run_parse",
        "prompt_chars": len(case["prompt"]),
        "grading_mode": grading.get("mode"),
        "requires_image": bool(case.get("requires_image")),
        "prompt_preview": case["prompt"][:240],
        "accurate": None,
    }


def run_direct_llm(case: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = make_llm(args.max_tokens, args.temperature)
    messages = [
        SystemMessage(content="直接解题，不要调用工具。回答必须以“最终答案：”开头。"),
        HumanMessage(content=build_prompt(case)),
    ]

    t0 = time.perf_counter()
    message = llm.invoke(messages)
    total_ms = (time.perf_counter() - t0) * 1000
    response = str(message.content)

    return {
        "case_id": case["id"],
        "question_no": case["question_no"],
        "type": case.get("type"),
        "method": "direct_llm",
        "scope": "LLM direct answer, no tool, no AgentCube sandbox",
        "total_ms": round(total_ms, 2),
        "response": response,
        "usage": usage_metadata(message),
        "grade": grade_response(case, response),
    }


def run_llm_tool_call_local_python(case: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    from langchain_core.tools import tool

    tool_timings = {}  # type: Dict[str, Any]

    @tool
    def run_python_code(code: str) -> str:
        """Run Python code locally and return stdout. Benchmark only; not safe for untrusted code."""
        blocked = [
            "__import__",
            "import os",
            "import pathlib",
            "import shutil",
            "import subprocess",
            "import socket",
            "import requests",
            "urllib",
            "open(",
            "eval(",
            "exec(",
            "compile(",
            "globals(",
            "locals(",
        ]
        if any(token in code for token in blocked):
            return "blocked unsafe local code"

        with tempfile.TemporaryDirectory(prefix="agentcube-gaokao-local-tool-") as tmpdir:
            script = Path(tmpdir) / "tool_code.py"
            script.write_text(code, encoding="utf-8")

            t0 = time.perf_counter()
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=tmpdir,
                env={"PYTHONNOUSERSITE": "1", "PATH": os.environ.get("PATH", "")},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=args.tool_timeout,
                check=False,
            )
            tool_timings["local_tool_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        if proc.returncode != 0:
            return f"exit_code={proc.returncode}\nstderr={proc.stderr.strip()}"
        return proc.stdout.strip()

    llm = make_llm(args.max_tokens, args.temperature)
    tool_llm = llm.bind_tools([run_python_code])
    messages = [
        SystemMessage(
            content=(
                "你必须调用 run_python_code 正好一次来做计算、枚举或数值验证，"
                "然后根据工具结果作答。最终答案必须以“最终答案：”开头。"
            )
        ),
        HumanMessage(content=build_prompt(case, prefer_tool=True)),
    ]

    t0 = time.perf_counter()
    tool_call_message = tool_llm.invoke(messages)
    tool_decision_ms = (time.perf_counter() - t0) * 1000
    messages.append(tool_call_message)

    tool_calls = getattr(tool_call_message, "tool_calls", None) or []
    if not tool_calls:
        response = str(tool_call_message.content)
        return {
            "case_id": case["id"],
            "question_no": case["question_no"],
            "type": case.get("type"),
            "method": "llm_tool_call_local_python",
            "scope": "LLM chose not to call local Python",
            "tool_decision_ms": round(tool_decision_ms, 2),
            "tool_call_count": 0,
            "response": response,
            "usage": usage_metadata(tool_call_message),
            "grade": grade_response(case, response),
        }

    tool_call = tool_calls[0]
    tool_output = run_python_code.invoke(tool_call["args"])
    messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call["id"]))

    t2 = time.perf_counter()
    final_message = llm.invoke([
        SystemMessage(content="根据原题和工具结果作答。回答必须以“最终答案：”开头。"),
        *messages,
    ])
    final_answer_ms = (time.perf_counter() - t2) * 1000
    response = str(final_message.content)

    total_ms = tool_decision_ms + tool_timings.get("local_tool_ms", 0) + final_answer_ms
    return {
        "case_id": case["id"],
        "question_no": case["question_no"],
        "type": case.get("type"),
        "method": "llm_tool_call_local_python",
        "scope": "LLM tool decision + local Python execution + LLM final answer",
        "tool_decision_ms": round(tool_decision_ms, 2),
        **tool_timings,
        "final_answer_ms": round(final_answer_ms, 2),
        "total_ms": round(total_ms, 2),
        "tool_call_count": len(tool_calls),
        "tool_output": tool_output,
        "response": response,
        "usage": {
            "tool_decision": usage_metadata(tool_call_message),
            "final_answer": usage_metadata(final_message),
        },
        "grade": grade_response(case, response),
    }


def run_llm_tool_call_agentcube(case: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    from agentcube import CodeInterpreterClient
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    from langchain_core.tools import tool

    tool_timings = {}  # type: Dict[str, Any]

    @tool
    def run_python_code(code: str) -> str:
        """Run Python code in an AgentCube CodeInterpreter sandbox and return stdout."""
        client = None
        try:
            t0 = time.perf_counter()
            client = CodeInterpreterClient(verbose=False, ttl=args.sandbox_ttl)
            create_ms = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            tool_error = None
            try:
                output = client.run_code("python", code, timeout=args.tool_timeout).strip()
            except Exception as exc:
                output = f"error={exc!r}"
                tool_error = repr(exc)
            run_ms = (time.perf_counter() - t1) * 1000

            session_id = client.session_id
            t2 = time.perf_counter()
            client.stop()
            client = None
            delete_ms = (time.perf_counter() - t2) * 1000

            timings = {
                "session_id_prefix": session_id[:8] if session_id else None,
                "create_session_ms": round(create_ms, 2),
                "run_code_ms": round(run_ms, 2),
                "delete_session_ms": round(delete_ms, 2),
                "agentcube_tool_ms": round(create_ms + run_ms + delete_ms, 2),
            }
            if tool_error:
                timings["tool_error"] = tool_error
            tool_timings.update(timings)
            return output
        finally:
            if client is not None:
                client.stop()

    llm = make_llm(args.max_tokens, args.temperature)
    tool_llm = llm.bind_tools([run_python_code])
    messages = [
        SystemMessage(
            content=(
                "你必须调用 run_python_code 正好一次来做计算、枚举或数值验证。"
                "该工具运行在 AgentCube sandbox 中。最终答案必须以“最终答案：”开头。"
            )
        ),
        HumanMessage(content=build_prompt(case, prefer_tool=True)),
    ]

    t0 = time.perf_counter()
    tool_call_message = tool_llm.invoke(messages)
    tool_decision_ms = (time.perf_counter() - t0) * 1000
    messages.append(tool_call_message)

    tool_calls = getattr(tool_call_message, "tool_calls", None) or []
    if not tool_calls:
        response = str(tool_call_message.content)
        return {
            "case_id": case["id"],
            "question_no": case["question_no"],
            "type": case.get("type"),
            "method": "llm_tool_call_agentcube",
            "scope": "LLM chose not to call AgentCube sandbox",
            "tool_decision_ms": round(tool_decision_ms, 2),
            "tool_call_count": 0,
            "response": response,
            "usage": usage_metadata(tool_call_message),
            "grade": grade_response(case, response),
        }

    tool_call = tool_calls[0]
    tool_output = run_python_code.invoke(tool_call["args"])
    messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call["id"]))

    t2 = time.perf_counter()
    final_message = llm.invoke([
        SystemMessage(content="根据原题和 AgentCube 工具结果作答。回答必须以“最终答案：”开头。"),
        *messages,
    ])
    final_answer_ms = (time.perf_counter() - t2) * 1000
    response = str(final_message.content)

    total_ms = tool_decision_ms + tool_timings.get("agentcube_tool_ms", 0) + final_answer_ms
    return {
        "case_id": case["id"],
        "question_no": case["question_no"],
        "type": case.get("type"),
        "method": "llm_tool_call_agentcube",
        "scope": "LLM tool decision + AgentCube sandbox Python + LLM final answer",
        "tool_decision_ms": round(tool_decision_ms, 2),
        **tool_timings,
        "final_answer_ms": round(final_answer_ms, 2),
        "total_ms": round(total_ms, 2),
        "tool_call_count": len(tool_calls),
        "tool_output": tool_output,
        "response": response,
        "usage": {
            "tool_decision": usage_metadata(tool_call_message),
            "final_answer": usage_metadata(final_message),
        },
        "grade": grade_response(case, response),
    }


def run_math_agent(case: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    import requests

    payload = {
        "query": build_prompt(case, prefer_tool=True),
        "thread_id": f"gaokao-{case['question_no']}-{int(time.time())}",
    }
    t0 = time.perf_counter()
    response = requests.post(args.math_agent_url, json=payload, timeout=args.http_timeout)
    total_ms = (time.perf_counter() - t0) * 1000
    try:
        data = response.json()
    except Exception:
        data = {"raw_response": response.text}
    answer = data.get("response", response.text)

    return {
        "case_id": case["id"],
        "question_no": case["question_no"],
        "type": case.get("type"),
        "method": "math_agent",
        "scope": "HTTP math-agent + LLM agent loop + AgentCube sandbox tool when selected",
        "http_status": response.status_code,
        "total_ms": round(total_ms, 2),
        "response": answer,
        "raw": data,
        "grade": grade_response(case, answer),
    }


RUNNERS = {
    "dry_run": run_dry_case,
    "direct_llm": run_direct_llm,
    "llm_tool_local_python": run_llm_tool_call_local_python,
    "llm_tool_agentcube": run_llm_tool_call_agentcube,
    "math_agent": run_math_agent,
}

ERROR_METHOD_NAMES = {
    "llm_tool_local_python": "llm_tool_call_local_python",
    "llm_tool_agentcube": "llm_tool_call_agentcube",
}


def run_one(case: Dict[str, Any], method: str, args: argparse.Namespace) -> Dict[str, Any]:
    runner = RUNNERS[method]
    try:
        if method == "dry_run":
            result = runner(case)
        else:
            result = runner(case, args)
        grade = result.get("grade")
        if grade and "accurate" not in result:
            result["accurate"] = grade.get("accurate")
        return result
    except Exception as exc:
        return {
            "case_id": case["id"],
            "question_no": case["question_no"],
            "type": case.get("type"),
            "method": ERROR_METHOD_NAMES.get(method, method),
            "error": repr(exc),
            "accurate": False,
        }


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_method = {}  # type: Dict[str, Dict[str, Any]]
    for result in results:
        method = result["method"]
        bucket = by_method.setdefault(method, {
            "total": 0,
            "auto_graded": 0,
            "correct": 0,
            "manual": 0,
            "errors": 0,
            "latencies_ms": [],
        })
        bucket["total"] += 1
        if result.get("error"):
            bucket["errors"] += 1
        accurate = result.get("accurate")
        if accurate is True:
            bucket["auto_graded"] += 1
            bucket["correct"] += 1
        elif accurate is False:
            bucket["auto_graded"] += 1
        elif accurate is None:
            bucket["manual"] += 1
        if "total_ms" in result:
            bucket["latencies_ms"].append(result["total_ms"])

    for bucket in by_method.values():
        latencies = bucket.pop("latencies_ms")
        if latencies:
            sorted_latencies = sorted(latencies)
            bucket["mean_ms"] = round(sum(latencies) / len(latencies), 2)
            bucket["p50_ms"] = sorted_latencies[len(sorted_latencies) // 2]
            bucket["max_ms"] = sorted_latencies[-1]
        if bucket["auto_graded"]:
            bucket["accuracy"] = round(bucket["correct"] / bucket["auto_graded"], 4)

    return by_method


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="Benchmark manifest JSON.")
    parser.add_argument("--questions-md", type=Path, default=None, help="Override markdown question source.")
    parser.add_argument("--case", default="", help="Comma-separated case ids or question numbers, e.g. 1,6,q13.")
    parser.add_argument("--types", default="", help="Comma-separated types, e.g. single_choice,fill_blank.")
    parser.add_argument("--limit", type=int, default=None, help="Limit selected cases.")
    parser.add_argument(
        "--methods",
        default="dry_run",
        help=(
            "Comma-separated methods: dry_run,direct_llm,llm_tool_local_python,"
            "llm_tool_agentcube,math_agent. Default: dry_run."
        ),
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="Optional env file for LLM config.")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON result to this path.")
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--tool-timeout", type=float, default=30)
    parser.add_argument("--sandbox-ttl", type=int, default=600)
    parser.add_argument("--http-timeout", type=float, default=180)
    parser.add_argument("--math-agent-url", default="http://localhost:18082/")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    methods = parse_csv(args.methods)
    unknown = [method for method in methods if method not in RUNNERS]
    if unknown:
        parser.error(f"unknown methods: {', '.join(unknown)}")

    load_env_file(args.env_file)

    cases = load_cases(args.cases.resolve(), args.questions_md)
    selected_cases = select_cases(cases, parse_csv(args.case), parse_csv(args.types), args.limit)
    if not selected_cases:
        parser.error("no cases selected")

    results = []
    for case in selected_cases:
        for method in methods:
            results.append(run_one(case, method, args))

    payload = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "cases_file": str(args.cases.resolve()),
        "methods": methods,
        "selected_case_count": len(selected_cases),
        "result_count": len(results),
        "summary": summarize(results),
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
