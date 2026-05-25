#!/usr/bin/env python3
"""
tests/test_llm_proxy.py

Test the LiteLLM proxy (/v1/) on all nodes listed in manifests/state.json.

Usage:
    # Test all nodes with a quick ping + one completion:
    uv run python tests/test_llm_proxy.py

    # Test a single node by name:
    uv run python tests/test_llm_proxy.py --node server-01

    # Override the model (must be in the LLM_KEYS pool):
    uv run python tests/test_llm_proxy.py --model gpt-4o-mini

    # Test streaming mode:
    uv run python tests/test_llm_proxy.py --stream

    # Verbose: print full response JSON:
    uv run python tests/test_llm_proxy.py --verbose
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve repo root and load state.json
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "manifests" / "state.json"

CHAT_PATH = "/v1/chat/completions"
MODELS_PATH = "/v1/models"
HEALTH_PATH = "/health"  # LiteLLM's built-in health endpoint (no /v1/ prefix)

DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_PROMPT = "Reply with exactly three words: the sky is."
TIMEOUT = 30


# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    DIM = "\033[2m"


def ok(msg):  return f"{C.GREEN}✓{C.RESET} {msg}"
def fail(msg): return f"{C.RED}✗{C.RESET} {msg}"
def warn(msg): return f"{C.YELLOW}!{C.RESET} {msg}"
def hdr(msg):  return f"{C.BOLD}{C.CYAN}{msg}{C.RESET}"


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no extra deps)
# ---------------------------------------------------------------------------
def _request(url: str, payload: dict | None = None, timeout: int = TIMEOUT) -> tuple[int, dict | str]:
    """Return (status_code, parsed_json_or_raw_str)."""
    data = json.dumps(payload).encode() if payload else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body
    except Exception as e:
        return 0, str(e)


def _stream_request(url: str, payload: dict, timeout: int = TIMEOUT) -> tuple[int, list[str]]:
    """Return (status_code, list_of_content_chunks) for a streaming SSE response."""
    payload = {**payload, "stream": True}
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    chunks = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            for raw_line in resp:
                line = raw_line.decode().strip()
                if not line.startswith("data:"):
                    continue
                payload_str = line[len("data:"):].strip()
                if payload_str == "[DONE]":
                    break
                try:
                    chunk_json = json.loads(payload_str)
                    delta = chunk_json["choices"][0]["delta"].get("content", "")
                    if delta:
                        chunks.append(delta)
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass
            return status, chunks
    except urllib.error.HTTPError as e:
        return e.code, [e.read().decode()]
    except Exception as e:
        return 0, [str(e)]


# ---------------------------------------------------------------------------
# Individual test steps
# ---------------------------------------------------------------------------
def test_health(base_url: str) -> bool:
    url = base_url.rstrip("/") + HEALTH_PATH
    status, body = _request(url)
    if status == 200:
        print(f"  {ok('health')}  {C.DIM}{url}{C.RESET}")
        return True
    else:
        print(f"  {fail('health')}  HTTP {status} — {url}")
        if isinstance(body, dict):
            print(f"    {C.DIM}{json.dumps(body, indent=2)[:200]}{C.RESET}")
        return False


def test_models(base_url: str, verbose: bool = False) -> bool:
    url = base_url.rstrip("/") + MODELS_PATH
    status, body = _request(url)
    if status == 200 and isinstance(body, dict):
        models = [m.get("id", "?") for m in body.get("data", [])]
        print(f"  {ok('models')}  {', '.join(models) or '(none listed)'}")
        if verbose:
            print(f"    {C.DIM}{json.dumps(body, indent=2)[:400]}{C.RESET}")
        return True
    else:
        print(f"  {fail('models')}  HTTP {status}")
        return False


def test_chat(base_url: str, model: str, prompt: str, verbose: bool = False) -> bool:
    url = base_url.rstrip("/") + CHAT_PATH
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 64,
    }
    t0 = time.monotonic()
    status, body = _request(url, payload)
    elapsed = time.monotonic() - t0

    if status == 200 and isinstance(body, dict):
        content = body["choices"][0]["message"]["content"].strip()
        usage = body.get("usage", {})
        tokens = usage.get("total_tokens", "?")
        print(f"  {ok('chat')}  [{elapsed:.1f}s, {tokens} tokens]  \"{content}\"")
        if verbose:
            print(f"    {C.DIM}{json.dumps(body, indent=2)[:600]}{C.RESET}")
        return True
    else:
        print(f"  {fail('chat')}  HTTP {status}")
        if isinstance(body, dict):
            err = body.get("error", body)
            print(f"    {C.RED}{json.dumps(err)[:300]}{C.RESET}")
        else:
            print(f"    {C.RED}{str(body)[:300]}{C.RESET}")
        return False


def test_chat_stream(base_url: str, model: str, prompt: str) -> bool:
    url = base_url.rstrip("/") + CHAT_PATH
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 64,
    }
    t0 = time.monotonic()
    status, chunks = _stream_request(url, payload)
    elapsed = time.monotonic() - t0

    if status == 200:
        content = "".join(chunks).strip()
        print(f"  {ok('stream')}  [{elapsed:.1f}s, {len(chunks)} chunks]  \"{content}\"")
        return True
    else:
        print(f"  {fail('stream')}  HTTP {status}  {chunks}")
        return False


def test_no_model(base_url: str) -> bool:
    """Verify the proxy returns 400 when 'model' field is omitted."""
    url = base_url.rstrip("/") + CHAT_PATH
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    status, body = _request(url, payload)
    if status in (400, 422):
        print(f"  {ok('no-model → 400')}  HTTP {status} (expected)")
        return True
    else:
        print(f"  {warn('no-model → 400')}  HTTP {status} (expected 400/422)")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def load_nodes(node_filter: str | None) -> dict[str, str]:
    """Return {node_name: base_url} from state.json, filtered if requested."""
    if not STATE_PATH.exists():
        print(fail(f"state.json not found at {STATE_PATH}"))
        sys.exit(1)
    with open(STATE_PATH) as f:
        state = json.load(f)

    nodes = {}
    for name, info in state.items():
        if node_filter and name != node_filter:
            continue
        url = info.get("url")
        if not url:
            continue
        # Only test nodes that have llm_proxy in their services list
        services = info.get("services", [])
        if "llm_proxy" not in services:
            print(warn(f"Skipping {name} — llm_proxy not in services list"))
            continue
        nodes[name] = url

    if not nodes:
        msg = f"No nodes with llm_proxy found"
        if node_filter:
            msg += f" matching '{node_filter}'"
        msg += ". Run 'make build && make deploy' first."
        print(fail(msg))
        sys.exit(1)

    return nodes


def run(args):
    nodes = load_nodes(args.node)
    results = {}

    for node_name, base_url in nodes.items():
        print(f"\n{hdr('━━━')} {hdr(node_name)}  {C.DIM}{base_url}{C.RESET}")

        passed = 0
        total = 0

        # 1. Health
        total += 1
        if test_health(base_url):
            passed += 1

        # 2. Models list
        total += 1
        if test_models(base_url, verbose=args.verbose):
            passed += 1

        # 3. No-model → 400
        total += 1
        if test_no_model(base_url):
            passed += 1

        # 4. Chat completion (streaming or regular)
        total += 1
        if args.stream:
            if test_chat_stream(base_url, args.model, DEFAULT_PROMPT):
                passed += 1
        else:
            if test_chat(base_url, args.model, DEFAULT_PROMPT, verbose=args.verbose):
                passed += 1

        results[node_name] = (passed, total)

    # Summary table
    print(f"\n{hdr('━━━━━━━━━━━━━━━━━━━━━━━━')}")
    print(hdr("  RESULTS SUMMARY"))
    print(hdr("━━━━━━━━━━━━━━━━━━━━━━━━"))
    all_pass = True
    for node_name, (passed, total) in results.items():
        colour = C.GREEN if passed == total else (C.YELLOW if passed > 0 else C.RED)
        bar = f"{colour}{passed}/{total}{C.RESET}"
        status_icon = "✓" if passed == total else ("!" if passed > 0 else "✗")
        print(f"  {colour}{status_icon}{C.RESET}  {node_name:<14}  {bar}")
        if passed < total:
            all_pass = False
    print()
    sys.exit(0 if all_pass else 1)


def main():
    parser = argparse.ArgumentParser(
        description="Test the LiteLLM proxy on deployed HF Space nodes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--node", metavar="NAME",
                        help="Test only this node (e.g. server-01)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Model to use in the chat test (default: {DEFAULT_MODEL})")
    parser.add_argument("--stream", action="store_true",
                        help="Use streaming mode for the chat test")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print full response JSON")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
