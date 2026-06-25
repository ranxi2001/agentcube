#!/usr/bin/env python3
"""White-box breakpoint test for PR #387 warm-pool data flow.

This is intentionally not a black-box math-agent E2E test.  It uses one
gaokao-style math problem only as the payload that flows through the system.
The assertions are placed on the real runtime objects:

  CodeInterpreter -> SandboxWarmPool -> SandboxClaim -> adopted Sandbox -> Pod
  -> Store-backed Router lookup -> PicoD /api/files and /api/execute.

Prerequisites:
  - A live AgentCube deployment with WorkloadManager and Router reachable.
  - A warm-pool CodeInterpreter, defaulting to e2e-code-interpreter-warmpool.
  - kubectl configured for the same cluster.

Example:
  WORKLOAD_MANAGER_URL=http://localhost:8080 \
  ROUTER_URL=http://localhost:8081 \
  AGENTCUBE_NAMESPACE=agentcube \
  python3 trace_math_dataflow_breakpoints.py --code-interpreter e2e-code-interpreter-warmpool --pause
"""

import argparse
import base64
import json
import os
import pdb
import subprocess
import sys
import time
import urllib.error
import urllib.request


SESSION_LABEL = "runtime.agentcube.io/session-id"
SANDBOX_KIND = "Sandbox"
SANDBOX_CLAIM_KIND = "SandboxClaim"
POD_NAME_ANNOTATIONS = (
    "agents.x-k8s.io/pod-name",
    "agents.x-k8s.io/sandbox-pod-name",
)

MATH_SCRIPT = r'''
import json

# Gaokao-style checkpoint problem:
# Find the maximum value of f(x)=x^3-3x on the interval [-2, 2].
# Critical points are x=-1 and x=1; endpoints are also checked.
def f(x):
    return x ** 3 - 3 * x

candidates = [-2, -1, 1, 2]
values = {str(x): f(x) for x in candidates}
answer = max(values.values())
result = {
    "problem": "max f(x)=x^3-3x on [-2,2]",
    "candidates": candidates,
    "values": values,
    "answer": answer,
}
print(json.dumps(result, sort_keys=True))
if answer != 2:
    raise SystemExit("unexpected answer: %s" % answer)
'''


class TraceFailure(Exception):
    pass


class Breakpoints(object):
    def __init__(self, pause=False, pdb_mode=False):
        self.pause = pause
        self.pdb_mode = pdb_mode
        self.index = 0

    def pass_(self, title, data=None):
        self.index += 1
        print("\n[BP%02d PASS] %s" % (self.index, title))
        if data is not None:
            print(json.dumps(data, indent=2, sort_keys=True))
        if self.pdb_mode:
            pdb.set_trace()
        elif self.pause:
            try:
                input("Press Enter to continue...")
            except EOFError:
                pass


def fail(message):
    raise TraceFailure(message)


def require(condition, message):
    if not condition:
        fail(message)


def json_dumps(data):
    return json.dumps(data, sort_keys=True).encode("utf-8")


def http_json(method, url, payload=None, headers=None, timeout=120):
    req_headers = dict(headers or {})
    body = None
    if payload is not None:
        body = json_dumps(payload)
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            text = raw.decode("utf-8") if raw else ""
            data = json.loads(text) if text else None
            return resp.getcode(), resp.headers, data
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        text = raw.decode("utf-8", "replace") if raw else ""
        raise TraceFailure("HTTP %s %s failed: %s %s" % (method, url, exc.code, text))
    except urllib.error.URLError as exc:
        raise TraceFailure("HTTP %s %s failed: %s" % (method, url, exc))


def kubectl_base(args):
    cmd = ["kubectl"]
    if args.kubeconfig:
        cmd.extend(["--kubeconfig", args.kubeconfig])
    return cmd


def run_kubectl(args, kubectl_args, allow_not_found=False):
    cmd = kubectl_base(args) + kubectl_args
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if allow_not_found and ("NotFound" in stderr or "not found" in stderr):
            return None
        raise TraceFailure("kubectl failed: %s\n%s" % (" ".join(cmd), stderr))
    return proc.stdout


def kubectl_json(args, kubectl_args, allow_not_found=False):
    out = run_kubectl(args, kubectl_args + ["-o", "json"], allow_not_found=allow_not_found)
    if out is None:
        return None
    return json.loads(out)


def get_resource(args, resource, namespace, name, allow_not_found=False):
    return kubectl_json(
        args,
        ["get", resource, "-n", namespace, name],
        allow_not_found=allow_not_found,
    )


def list_resource(args, resource, namespace, selector=None):
    cmd = ["get", resource, "-n", namespace]
    if selector:
        cmd.extend(["-l", selector])
    return kubectl_json(args, cmd).get("items", [])


def poll(description, fn, timeout=120, interval=1.0):
    deadline = time.time() + timeout
    last_error = None
    while time.time() <= deadline:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - preserve last assertion for diagnostics.
            last_error = exc
            time.sleep(interval)
    raise TraceFailure("timed out waiting for %s: %s" % (description, last_error))


def owner_ref(obj, kind, name=None):
    refs = obj.get("metadata", {}).get("ownerReferences") or []
    for ref in refs:
        if ref.get("kind") == kind and (name is None or ref.get("name") == name):
            return ref
    return None


def ready_condition(obj):
    for cond in obj.get("status", {}).get("conditions") or []:
        if cond.get("type") == "Ready" and cond.get("status") == "True":
            return cond
    return None


def pod_ready(obj):
    return ready_condition(obj) is not None


def endpoint_host(endpoint):
    if "://" in endpoint:
        endpoint = endpoint.split("://", 1)[1]
    if endpoint.startswith("["):
        return endpoint.split("]", 1)[0].lstrip("[")
    return endpoint.rsplit(":", 1)[0]


def object_summary(obj):
    meta = obj.get("metadata", {})
    return {
        "kind": obj.get("kind"),
        "namespace": meta.get("namespace"),
        "name": meta.get("name"),
        "uid": meta.get("uid"),
        "resourceVersion": meta.get("resourceVersion"),
    }


def auth_headers(args):
    if not args.api_token:
        return {}
    return {"Authorization": "Bearer %s" % args.api_token}


def create_session(args, bp):
    url = args.workload_manager_url.rstrip("/") + "/v1/code-interpreter"
    payload = {
        "name": args.code_interpreter,
        "namespace": args.namespace,
    }
    status, _headers, data = http_json("POST", url, payload, auth_headers(args), args.http_timeout)
    require(status == 200, "WorkloadManager create returned HTTP %s" % status)
    require(data and data.get("sessionId"), "create response missing sessionId")
    require(data.get("kind") == SANDBOX_CLAIM_KIND, "expected warm-pool kind SandboxClaim, got %r" % data.get("kind"))
    require(data.get("sandboxId"), "create response missing adopted sandbox UID")
    require(data.get("entryPoints"), "create response missing entryPoints")
    bp.pass_("WorkloadManager created warm-pool session", data)
    return data


def find_claim_by_session(args, session_id):
    selector = "%s=%s" % (SESSION_LABEL, session_id)

    def _find():
        items = list_resource(args, "sandboxclaims.extensions.agents.x-k8s.io", args.namespace, selector)
        require(len(items) == 1, "expected one SandboxClaim with %s, found %d" % (selector, len(items)))
        return items[0]

    return poll("SandboxClaim by session label", _find, args.k8s_timeout)


def wait_claim_adoption(args, claim_name):
    def _adopted():
        claim = get_resource(args, "sandboxclaims.extensions.agents.x-k8s.io", args.namespace, claim_name)
        sandbox = (claim.get("status") or {}).get("sandbox") or {}
        require(sandbox.get("name"), "claim.status.sandbox.name is still empty")
        pod_ips = sandbox.get("podIPs") or []
        require(pod_ips, "claim.status.sandbox.podIPs is still empty")
        return claim

    return poll("SandboxClaim status adoption", _adopted, args.k8s_timeout)


def resolve_pod_name(sandbox):
    annotations = sandbox.get("metadata", {}).get("annotations") or {}
    for key in POD_NAME_ANNOTATIONS:
        if annotations.get(key):
            return annotations[key]
    return None


def find_pod_for_sandbox(args, sandbox_name):
    pod_name = None
    sandbox = get_resource(args, "sandboxes.agents.x-k8s.io", args.namespace, sandbox_name)
    pod_name = resolve_pod_name(sandbox)
    if pod_name:
        return get_resource(args, "pods", args.namespace, pod_name)

    def _find():
        pods = list_resource(args, "pods", args.namespace)
        owned = [pod for pod in pods if owner_ref(pod, SANDBOX_KIND, sandbox_name)]
        require(len(owned) == 1, "expected one Pod owned by Sandbox/%s, found %d" % (sandbox_name, len(owned)))
        return owned[0]

    return poll("Pod ownerRef fallback", _find, args.k8s_timeout)


def assert_adopted_sandbox(args, bp, claim, create_response):
    claim_name = claim["metadata"]["name"]
    claim_uid = claim["metadata"]["uid"]
    adopted_name = claim["status"]["sandbox"]["name"]
    sandbox = get_resource(args, "sandboxes.agents.x-k8s.io", args.namespace, adopted_name)

    require(sandbox["metadata"].get("uid") == create_response.get("sandboxId"),
            "create response sandboxId does not match adopted Sandbox UID")
    ref = owner_ref(sandbox, SANDBOX_CLAIM_KIND, claim_name)
    require(ref is not None, "adopted Sandbox ownerRef is not SandboxClaim/%s" % claim_name)
    require(ref.get("uid") == claim_uid, "adopted Sandbox ownerRef UID does not match claim UID")
    require(ready_condition(sandbox) is not None, "adopted Sandbox is not Ready")

    bp.pass_("SandboxClaim points to adopted Sandbox", {
        "claim": object_summary(claim),
        "adoptedSandbox": object_summary(sandbox),
        "claimStatusSandbox": claim["status"]["sandbox"],
        "sandboxOwnerRef": ref,
        "podNameAnnotation": resolve_pod_name(sandbox),
    })
    return sandbox


def assert_pod(args, bp, claim, sandbox, create_response):
    pod = find_pod_for_sandbox(args, sandbox["metadata"]["name"])
    pod_ip = pod.get("status", {}).get("podIP")
    require(pod_ready(pod), "adopted Pod is not Ready")
    require(pod_ip, "adopted Pod has no podIP")

    pod_ref = owner_ref(pod, SANDBOX_KIND, sandbox["metadata"]["name"])
    require(pod_ref is not None, "Pod ownerRef is not Sandbox/%s" % sandbox["metadata"]["name"])
    require(pod_ref.get("uid") == sandbox["metadata"].get("uid"), "Pod ownerRef UID does not match Sandbox UID")

    claim_pod_ips = claim["status"]["sandbox"].get("podIPs") or []
    require(pod_ip in claim_pod_ips, "Pod IP %s not found in claim.status.sandbox.podIPs %r" % (pod_ip, claim_pod_ips))

    endpoints = create_response.get("entryPoints") or []
    endpoint_hosts = [endpoint_host(ep.get("endpoint", "")) for ep in endpoints]
    require(pod_ip in endpoint_hosts, "Pod IP %s not found in create response entryPoints %r" % (pod_ip, endpoints))

    bp.pass_("Adopted Pod matches Sandbox, claim status, and entrypoint", {
        "pod": object_summary(pod),
        "podIP": pod_ip,
        "podOwnerRef": pod_ref,
        "claimPodIPs": claim_pod_ips,
        "entryPoints": endpoints,
    })
    return pod


def router_base(args):
    return "%s/v1/namespaces/%s/code-interpreters/%s/invocations" % (
        args.router_url.rstrip("/"),
        args.namespace,
        args.code_interpreter,
    )


def router_headers(args, session_id):
    headers = auth_headers(args)
    headers["x-agentcube-session-id"] = session_id
    return headers


def upload_math_script(args, bp, session_id, script_name):
    url = router_base(args) + "/api/files"
    content = base64.b64encode(MATH_SCRIPT.encode("utf-8")).decode("ascii")
    payload = {
        "path": script_name,
        "content": content,
        "mode": "0644",
    }
    status, headers, data = http_json("POST", url, payload, router_headers(args, session_id), args.http_timeout)
    require(status == 200, "Router /api/files returned HTTP %s" % status)
    returned_session = headers.get("x-agentcube-session-id")
    require(returned_session == session_id, "Router response session header %r != %r" % (returned_session, session_id))
    require(data and data.get("path") == script_name, "PicoD file response did not confirm script path")
    bp.pass_("Router used Store entrypoint and PicoD wrote math script", {
        "url": url,
        "responseSessionHeader": returned_session,
        "fileInfo": data,
    })


def execute_math_script(args, bp, session_id, script_name):
    url = router_base(args) + "/api/execute"
    payload = {
        "command": ["python3", script_name],
        "timeout": "30s",
    }
    status, headers, data = http_json("POST", url, payload, router_headers(args, session_id), args.http_timeout)
    require(status == 200, "Router /api/execute returned HTTP %s" % status)
    returned_session = headers.get("x-agentcube-session-id")
    require(returned_session == session_id, "Router response session header %r != %r" % (returned_session, session_id))
    require(data and data.get("exit_code") == 0, "PicoD execute failed: %r" % data)

    stdout = data.get("stdout") or ""
    try:
        result = json.loads(stdout.strip().splitlines()[-1])
    except (IndexError, ValueError) as exc:
        raise TraceFailure("failed to parse PicoD stdout as math result JSON: %r (%s)" % (stdout, exc))
    require(result.get("answer") == 2, "math checkpoint answer mismatch: %r" % result)
    bp.pass_("PicoD executed gaokao-style math payload and returned answer", {
        "url": url,
        "responseSessionHeader": returned_session,
        "execute": {
            "exit_code": data.get("exit_code"),
            "stdout": stdout,
            "stderr": data.get("stderr"),
        },
        "mathResult": result,
    })


def delete_session(args, bp, session_id, claim_name, sandbox_name, pod_name):
    url = args.workload_manager_url.rstrip("/") + "/v1/code-interpreter/sessions/" + session_id
    status, _headers, data = http_json("DELETE", url, None, auth_headers(args), args.http_timeout)
    require(status == 200, "WorkloadManager delete returned HTTP %s" % status)
    bp.pass_("WorkloadManager accepted session delete", data)

    def _deleted_claim():
        obj = get_resource(args, "sandboxclaims.extensions.agents.x-k8s.io", args.namespace, claim_name, allow_not_found=True)
        require(obj is None, "SandboxClaim/%s still exists" % claim_name)
        return True

    def _deleted_sandbox():
        obj = get_resource(args, "sandboxes.agents.x-k8s.io", args.namespace, sandbox_name, allow_not_found=True)
        require(obj is None, "Sandbox/%s still exists" % sandbox_name)
        return True

    def _deleted_pod():
        obj = get_resource(args, "pods", args.namespace, pod_name, allow_not_found=True)
        require(obj is None, "Pod/%s still exists" % pod_name)
        return True

    poll("SandboxClaim deletion", _deleted_claim, args.k8s_timeout)
    poll("adopted Sandbox deletion", _deleted_sandbox, args.k8s_timeout)
    poll("adopted Pod deletion", _deleted_pod, args.k8s_timeout)

    warm_pool = get_resource(
        args,
        "sandboxwarmpools.extensions.agents.x-k8s.io",
        args.namespace,
        args.code_interpreter,
        allow_not_found=True,
    )
    warm_pool_summary = None
    if warm_pool is not None:
        status_obj = warm_pool.get("status") or {}
        spec_obj = warm_pool.get("spec") or {}
        ready = status_obj.get("readyReplicas")
        replicas = spec_obj.get("replicas")
        if replicas is not None:
            require(ready == replicas, "warm pool did not refill: readyReplicas=%r replicas=%r" % (ready, replicas))
        warm_pool_summary = {
            "name": warm_pool["metadata"]["name"],
            "readyReplicas": ready,
            "replicas": replicas,
        }

    bp.pass_("Delete/GC removed adopted runtime objects and warm pool is refilled", {
        "deleted": {
            "SandboxClaim": claim_name,
            "Sandbox": sandbox_name,
            "Pod": pod_name,
        },
        "warmPool": warm_pool_summary,
    })


def check_preconditions(args, bp):
    require(args.workload_manager_url, "WORKLOAD_MANAGER_URL or --workload-manager-url is required")
    require(args.router_url, "ROUTER_URL or --router-url is required")

    ci = get_resource(
        args,
        "codeinterpreters.runtime.agentcube.volcano.sh",
        args.namespace,
        args.code_interpreter,
    )
    warm_pool_size = ((ci.get("spec") or {}).get("warmPoolSize"))
    require(warm_pool_size and int(warm_pool_size) > 0,
            "CodeInterpreter/%s is not configured with warmPoolSize > 0" % args.code_interpreter)

    warm_pool = get_resource(
        args,
        "sandboxwarmpools.extensions.agents.x-k8s.io",
        args.namespace,
        args.code_interpreter,
    )
    ready = (warm_pool.get("status") or {}).get("readyReplicas")
    require(ready and int(ready) > 0, "SandboxWarmPool/%s has no ready replicas" % args.code_interpreter)

    bp.pass_("Preconditions: live warm-pool CodeInterpreter is ready", {
        "namespace": args.namespace,
        "codeInterpreter": object_summary(ci),
        "warmPool": {
            "name": warm_pool["metadata"]["name"],
            "readyReplicas": ready,
            "replicas": (warm_pool.get("spec") or {}).get("replicas"),
        },
        "workloadManagerURL": args.workload_manager_url,
        "routerURL": args.router_url,
    })


def parse_args():
    parser = argparse.ArgumentParser(description="Trace PR #387 warm-pool data flow with breakpoint assertions.")
    parser.add_argument("--namespace", default=os.getenv("AGENTCUBE_NAMESPACE", "agentcube"))
    parser.add_argument("--code-interpreter", default=os.getenv("CODE_INTERPRETER_NAME", "e2e-code-interpreter-warmpool"))
    parser.add_argument("--workload-manager-url", default=os.getenv("WORKLOAD_MANAGER_URL"))
    parser.add_argument("--router-url", default=os.getenv("ROUTER_URL"))
    parser.add_argument("--api-token", default=os.getenv("API_TOKEN"))
    parser.add_argument("--kubeconfig", default=None, help="optional explicit kubeconfig path; otherwise kubectl uses its normal context/env")
    parser.add_argument("--http-timeout", type=int, default=120)
    parser.add_argument("--k8s-timeout", type=int, default=120)
    parser.add_argument("--pause", action="store_true", help="pause after every passed breakpoint")
    parser.add_argument("--pdb", action="store_true", help="enter pdb.set_trace() after every passed checkpoint")
    parser.add_argument("--keep-session", action="store_true", help="do not delete the created session")
    return parser.parse_args()


def main():
    args = parse_args()
    bp = Breakpoints(pause=args.pause, pdb_mode=args.pdb)
    session_id = None
    claim_name = None
    sandbox_name = None
    pod_name = None

    try:
        check_preconditions(args, bp)
        create_response = create_session(args, bp)
        session_id = create_response["sessionId"]

        claim = find_claim_by_session(args, session_id)
        claim_name = claim["metadata"]["name"]
        require(create_response.get("sandboxName") == claim_name,
                "create response sandboxName %r does not match SandboxClaim name %r"
                % (create_response.get("sandboxName"), claim_name))
        bp.pass_("Created SandboxClaim is discoverable by session label", {
            "sessionId": session_id,
            "claim": object_summary(claim),
            "createResponseSandboxName": create_response.get("sandboxName"),
        })

        claim = wait_claim_adoption(args, claim_name)
        sandbox = assert_adopted_sandbox(args, bp, claim, create_response)
        sandbox_name = sandbox["metadata"]["name"]

        pod = assert_pod(args, bp, claim, sandbox, create_response)
        pod_name = pod["metadata"]["name"]

        script_name = "gaokao_trace_%s.py" % session_id.replace("-", "")[:12]
        upload_math_script(args, bp, session_id, script_name)
        execute_math_script(args, bp, session_id, script_name)

        if args.keep_session:
            bp.pass_("Session kept for manual inspection", {
                "sessionId": session_id,
                "claim": claim_name,
                "sandbox": sandbox_name,
                "pod": pod_name,
            })
        else:
            delete_session(args, bp, session_id, claim_name, sandbox_name, pod_name)
            session_id = None

        print("\nTRACE DATAFLOW TEST PASSED")
        return 0
    except TraceFailure as exc:
        print("\nTRACE DATAFLOW TEST FAILED: %s" % exc, file=sys.stderr)
        return 1
    finally:
        if session_id and not args.keep_session:
            try:
                url = args.workload_manager_url.rstrip("/") + "/v1/code-interpreter/sessions/" + session_id
                http_json("DELETE", url, None, auth_headers(args), args.http_timeout)
                print("cleanup: deleted session %s" % session_id)
            except Exception as exc:  # noqa: BLE001 - best-effort cleanup.
                print("cleanup: failed to delete session %s: %s" % (session_id, exc), file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
