import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from heapq import heappop, heappush
from pathlib import Path

import requests
from agentcube import CodeInterpreterClient
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


EDGES = [
    ("A", "B", 4), ("A", "C", 2), ("B", "C", 1), ("B", "D", 5),
    ("C", "D", 8), ("C", "E", 10), ("D", "E", 2), ("D", "F", 6),
    ("E", "F", 2), ("E", "G", 3), ("F", "H", 1), ("G", "H", 4),
    ("G", "I", 6), ("H", "I", 2), ("I", "J", 3), ("F", "J", 9),
    ("B", "G", 12),
]
EXPECTED_PATH = ["A", "C", "B", "D", "E", "F", "H", "I", "J"]
EXPECTED_WEIGHT = 18
QUERY = (
    "Graph has 10 nodes A,B,C,D,E,F,G,H,I,J and undirected weighted edges: "
    "A-B 4, A-C 2, B-C 1, B-D 5, C-D 8, C-E 10, D-E 2, D-F 6, "
    "E-F 2, E-G 3, F-H 1, G-H 4, G-I 6, H-I 2, I-J 3, F-J 9, B-G 12. "
    "Find the shortest path from A to J. Reply with only path and total weight."
)


def solve_local():
    graph = {}
    for u, v, w in EDGES:
        graph.setdefault(u, []).append((v, w))
        graph.setdefault(v, []).append((u, w))

    pq = [(0, "A", ["A"])]
    seen = {}
    while pq:
        dist, node, path = heappop(pq)
        if node in seen and seen[node] <= dist:
            continue
        seen[node] = dist
        if node == "J":
            return {"path": path, "weight": dist}
        for nxt, weight in graph.get(node, []):
            heappush(pq, (dist + weight, nxt, path + [nxt]))
    raise RuntimeError("no path")


def is_accurate_result(result):
    return result.get("path") == EXPECTED_PATH and result.get("weight") == EXPECTED_WEIGHT


def is_accurate_text(text):
    text = text or ""
    compact = re.sub(r"[^A-Z0-9]+", " ", text.upper())
    has_weight = bool(re.search(r"\b18\b", compact))
    ordered_path = " ".join(EXPECTED_PATH) in compact
    arrow_path = "A -> C -> B -> D -> E -> F -> H -> I -> J" in text
    return bool(has_weight and (ordered_path or arrow_path))


def run_local_python():
    t0 = time.perf_counter()
    single = solve_local()
    single_ms = (time.perf_counter() - t0) * 1000

    samples = []
    for _ in range(10000):
        start = time.perf_counter()
        solve_local()
        samples.append((time.perf_counter() - start) * 1000)

    return {
        "method": "local_python_algorithm",
        "scope": "pure local algorithm, no LLM, no network",
        "single_run_ms": round(single_ms, 4),
        "mean_ms_10000_runs": round(statistics.mean(samples), 4),
        "p95_ms_10000_runs": round(statistics.quantiles(samples, n=20)[18], 4),
        "result": single,
        "accurate": is_accurate_result(single),
    }


def run_direct_llm():
    llm = ChatOpenAI(
        model=os.environ["OPENAI_MODEL"],
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_API_BASE"],
        temperature=0.1,
        max_tokens=160,
    )
    t0 = time.perf_counter()
    message = llm.invoke([
        SystemMessage(content="Solve the graph problem directly. Do not call tools. Be concise."),
        HumanMessage(content=QUERY),
    ])
    elapsed_ms = (time.perf_counter() - t0) * 1000
    response = str(message.content)
    return {
        "method": "direct_llm_no_tool",
        "scope": "LLM direct answer, no AgentCube tool",
        "total_ms": round(elapsed_ms, 2),
        "response": response,
        "accurate": is_accurate_text(response),
    }


def run_agentcube_sdk_sandbox():
    sandbox_code = """
import json
from heapq import heappop, heappush

edges = [
    ("A", "B", 4), ("A", "C", 2), ("B", "C", 1), ("B", "D", 5),
    ("C", "D", 8), ("C", "E", 10), ("D", "E", 2), ("D", "F", 6),
    ("E", "F", 2), ("E", "G", 3), ("F", "H", 1), ("G", "H", 4),
    ("G", "I", 6), ("H", "I", 2), ("I", "J", 3), ("F", "J", 9),
    ("B", "G", 12),
]

graph = {}
for u, v, w in edges:
    graph.setdefault(u, []).append((v, w))
    graph.setdefault(v, []).append((u, w))

pq = [(0, "A", ["A"])]
seen = {}
while pq:
    dist, node, path = heappop(pq)
    if node in seen and seen[node] <= dist:
        continue
    seen[node] = dist
    if node == "J":
        print(json.dumps({"path": path, "weight": dist}))
        break
    for nxt, weight in graph.get(node, []):
        heappush(pq, (dist + weight, nxt, path + [nxt]))
"""

    client = None
    try:
        t0 = time.perf_counter()
        client = CodeInterpreterClient(verbose=False, ttl=600)
        create_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        output = client.run_code("python", sandbox_code, timeout=20).strip()
        run_ms = (time.perf_counter() - t1) * 1000

        session_id = client.session_id
        t2 = time.perf_counter()
        client.stop()
        client = None
        delete_ms = (time.perf_counter() - t2) * 1000

        parsed = json.loads(output)
        return {
            "method": "agentcube_sdk_sandbox_python",
            "scope": "AgentCube session create + router + sandbox Python + delete, no LLM",
            "session_id_prefix": session_id[:8] if session_id else None,
            "create_session_ms": round(create_ms, 2),
            "run_code_ms": round(run_ms, 2),
            "delete_session_ms": round(delete_ms, 2),
            "total_ms": round(create_ms + run_ms + delete_ms, 2),
            "result": parsed,
            "accurate": is_accurate_result(parsed),
        }
    finally:
        if client is not None:
            client.stop()


def run_llm_tool_call_agentcube_sdk():
    """Measure a direct LLM tool-calling flow without the math-agent HTTP wrapper."""
    tool_timings = {}

    @tool
    def run_python_code(code: str) -> str:
        """Run Python code in an AgentCube CodeInterpreter sandbox and return stdout."""
        client = None
        try:
            t0 = time.perf_counter()
            client = CodeInterpreterClient(verbose=False, ttl=600)
            create_ms = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            output = client.run_code("python", code, timeout=20).strip()
            run_ms = (time.perf_counter() - t1) * 1000

            session_id = client.session_id
            t2 = time.perf_counter()
            client.stop()
            client = None
            delete_ms = (time.perf_counter() - t2) * 1000

            tool_timings.update({
                "session_id_prefix": session_id[:8] if session_id else None,
                "create_session_ms": round(create_ms, 2),
                "run_code_ms": round(run_ms, 2),
                "delete_session_ms": round(delete_ms, 2),
                "agentcube_tool_ms": round(create_ms + run_ms + delete_ms, 2),
            })
            return output
        finally:
            if client is not None:
                client.stop()

    llm = ChatOpenAI(
        model=os.environ["OPENAI_MODEL"],
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_API_BASE"],
        temperature=0.1,
        max_tokens=240,
    )
    tool_llm = llm.bind_tools([run_python_code])

    messages = [
        SystemMessage(
            content=(
                "You solve graph problems by calling run_python_code exactly once. "
                "Put the graph in Python, run Dijkstra, and use the tool result."
            )
        ),
        HumanMessage(content=QUERY),
    ]

    t0 = time.perf_counter()
    tool_call_message = tool_llm.invoke(messages)
    tool_decision_ms = (time.perf_counter() - t0) * 1000
    messages.append(tool_call_message)

    if not tool_call_message.tool_calls:
        response = str(tool_call_message.content)
        return {
            "method": "llm_tool_call_agentcube_sdk",
            "scope": "LLM requested no tool, so AgentCube was not exercised",
            "tool_decision_ms": round(tool_decision_ms, 2),
            "response": response,
            "accurate": is_accurate_text(response),
        }

    # Execute only the first tool call; the prompt asks for exactly one.
    tool_call = tool_call_message.tool_calls[0]
    tool_output = run_python_code.invoke(tool_call["args"])

    # LangChain messages need a ToolMessage with the tool_call_id.
    from langchain_core.messages import ToolMessage

    messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call["id"]))

    t2 = time.perf_counter()
    final_message = llm.invoke([
        SystemMessage(content="Use the tool result to answer with only path and total weight."),
        *messages,
    ])
    final_answer_ms = (time.perf_counter() - t2) * 1000
    response = str(final_message.content)

    total_ms = tool_decision_ms + tool_timings.get("agentcube_tool_ms", 0) + final_answer_ms
    return {
        "method": "llm_tool_call_agentcube_sdk",
        "scope": "LLM tool decision + AgentCube sandbox Python + LLM final answer, no math-agent HTTP wrapper",
        "tool_decision_ms": round(tool_decision_ms, 2),
        **tool_timings,
        "final_answer_ms": round(final_answer_ms, 2),
        "total_ms": round(total_ms, 2),
        "tool_output": tool_output,
        "response": response,
        "accurate": is_accurate_text(response) or is_accurate_text(tool_output),
    }


def run_llm_tool_call_local_python():
    """Measure the same tool-calling flow with local Python instead of AgentCube."""
    tool_timings = {}

    @tool
    def run_python_code(code: str) -> str:
        """Run Python code locally and return stdout. Benchmark only; not safe for untrusted code."""
        blocked = [
            "__import__",
            "import os",
            "import subprocess",
            "import socket",
            "import requests",
            "urllib",
            "open(",
            "eval(",
            "exec(",
        ]
        if any(token in code for token in blocked):
            return "blocked unsafe local code"

        with tempfile.TemporaryDirectory(prefix="agentcube-local-tool-") as tmpdir:
            script = Path(tmpdir) / "tool_code.py"
            script.write_text(code, encoding="utf-8")

            t0 = time.perf_counter()
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=tmpdir,
                env={"PYTHONNOUSERSITE": "1"},
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            local_tool_ms = (time.perf_counter() - t0) * 1000

        tool_timings["local_tool_ms"] = round(local_tool_ms, 2)
        if proc.returncode != 0:
            return f"exit_code={proc.returncode}\nstderr={proc.stderr.strip()}"
        return proc.stdout.strip()

    llm = ChatOpenAI(
        model=os.environ["OPENAI_MODEL"],
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_API_BASE"],
        temperature=0.1,
        max_tokens=240,
    )
    tool_llm = llm.bind_tools([run_python_code])

    messages = [
        SystemMessage(
            content=(
                "You solve graph problems by calling run_python_code exactly once. "
                "Put the graph in Python, run Dijkstra, and use the tool result."
            )
        ),
        HumanMessage(content=QUERY),
    ]

    t0 = time.perf_counter()
    tool_call_message = tool_llm.invoke(messages)
    tool_decision_ms = (time.perf_counter() - t0) * 1000
    messages.append(tool_call_message)

    if not tool_call_message.tool_calls:
        response = str(tool_call_message.content)
        return {
            "method": "llm_tool_call_local_python",
            "scope": "LLM requested no tool, so local Python was not exercised",
            "tool_decision_ms": round(tool_decision_ms, 2),
            "response": response,
            "accurate": is_accurate_text(response),
        }

    tool_call = tool_call_message.tool_calls[0]
    tool_output = run_python_code.invoke(tool_call["args"])
    messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call["id"]))

    t2 = time.perf_counter()
    final_message = llm.invoke([
        SystemMessage(content="Use the tool result to answer with only path and total weight."),
        *messages,
    ])
    final_answer_ms = (time.perf_counter() - t2) * 1000
    response = str(final_message.content)

    total_ms = tool_decision_ms + tool_timings.get("local_tool_ms", 0) + final_answer_ms
    return {
        "method": "llm_tool_call_local_python",
        "scope": "LLM tool decision + local Python execution + LLM final answer, no AgentCube sandbox",
        "tool_decision_ms": round(tool_decision_ms, 2),
        **tool_timings,
        "final_answer_ms": round(final_answer_ms, 2),
        "total_ms": round(total_ms, 2),
        "tool_output": tool_output,
        "response": response,
        "accurate": is_accurate_text(response) or is_accurate_text(tool_output),
    }


def run_math_agent_end_to_end():
    payload = {
        "query": "Use the Python tool once to solve this shortest path problem. " + QUERY,
        "thread_id": "benchmark_shortest_path_once",
    }
    t0 = time.perf_counter()
    response = requests.post("http://localhost:18082/", json=payload, timeout=180)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    data = response.json()
    answer = data.get("response", "")
    return {
        "method": "math_agent_end_to_end_llm_tool_agentcube",
        "scope": "HTTP math-agent + LLM tool decision + AgentCube sandbox Python",
        "http_status": response.status_code,
        "total_ms": round(elapsed_ms, 2),
        "response": answer,
        "accurate": is_accurate_text(answer),
    }


def main():
    results = []
    for runner in [
        run_local_python,
        run_direct_llm,
        run_agentcube_sdk_sandbox,
        run_llm_tool_call_local_python,
        run_llm_tool_call_agentcube_sdk,
        run_math_agent_end_to_end,
    ]:
        try:
            results.append(runner())
        except Exception as exc:
            results.append({
                "method": runner.__name__.replace("run_", ""),
                "error": repr(exc),
                "accurate": False,
            })

    print(json.dumps({
        "expected": {"path": EXPECTED_PATH, "weight": EXPECTED_WEIGHT},
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
