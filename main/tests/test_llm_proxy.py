#!/usr/bin/env python3
"""
tests/test_llm_proxy.py

Test the LiteLLM proxy (/v1/) on deployed HF Space nodes.

Usage:
    uv run python tests/test_llm_proxy.py                        # servers 1 & 2 only
    uv run python tests/test_llm_proxy.py --all                  # all nodes
    uv run python tests/test_llm_proxy.py --node server-01       # single node
    uv run python tests/test_llm_proxy.py --model openai/gpt-oss-120b
    uv run python tests/test_llm_proxy.py --stream
    uv run python tests/test_llm_proxy.py --verbose

LLM keys are configured via llm_keys.yaml in the repository root.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT.parent / "manifests" / "state.json"

# Load .env for LITELLM_MASTER_KEY
load_dotenv(REPO_ROOT / ".env")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")

CHAT_PATH = "/v1/chat/completions"
MODELS_PATH = "/v1/models"
HEALTH_PATH = "/health"

DEFAULT_NODES = ["server-01", "server-02"]
DEFAULT_MODEL = "gemini/gemini-3.5-flash"
DEFAULT_PROMPT = "Who are you?"
TIMEOUT = 15


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
    MAGENTA = "\033[95m"


def ok(msg):
    return f"{C.GREEN}✓{C.RESET} {msg}"


def fail(msg):
    return f"{C.RED}✗{C.RESET} {msg}"


def warn(msg):
    return f"{C.YELLOW}!{C.RESET} {msg}"


def hdr(msg):
    return f"{C.BOLD}{C.CYAN}{msg}{C.RESET}"


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------
def _request(url: str, payload: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode() if payload else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if LITELLM_MASTER_KEY:
        headers["Authorization"] = f"Bearer {LITELLM_MASTER_KEY}"
    req = urllib.request.Request(
        url, data=data, headers=headers, method="POST" if data else "GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body)
            except:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except:
            return e.code, body
    except Exception as e:
        return 0, str(e)


def _stream_request(url: str, payload: dict) -> tuple[int, list[str]]:
    payload = {**payload, "stream": True}
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    chunks = []
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            for raw in resp:
                line = raw.decode().strip()
                if not line.startswith("data:"):
                    continue
                s = line[5:].strip()
                if s == "[DONE]":
                    break
                try:
                    delta = json.loads(s)["choices"][0]["delta"].get("content", "")
                    if delta:
                        chunks.append(delta)
                except:
                    pass
            return status, chunks
    except urllib.error.HTTPError as e:
        return e.code, [e.read().decode()]
    except Exception as e:
        return 0, [str(e)]


# ---------------------------------------------------------------------------
# Test steps
# ---------------------------------------------------------------------------
def test_health(base: str) -> bool:
    status, body = _request(base.rstrip("/") + HEALTH_PATH)
    if status == 200:
        print(f"  {ok('health')}  HTTP 200")
        return True
    print(f"  {fail('health')}  HTTP {status}")
    return False


def test_models(base: str) -> tuple[bool, list[str]]:
    """GET /v1/models — print each model id."""
    status, body = _request(base.rstrip("/") + MODELS_PATH)
    if status == 200 and isinstance(body, dict):
        models = body.get("data", [])
        ids = [m.get("id", "?") for m in models]
        print(f"  {ok('models')}  {len(ids)} model(s) available:")
        for m in models:
            mid = m.get("id", "?")
            owner = m.get("owned_by", "")
            extra = f"  {C.DIM}(owned_by: {owner}){C.RESET}" if owner else ""
            print(f"      {C.MAGENTA}→{C.RESET} {mid}{extra}")
        return True, ids
    print(f"  {fail('models')}  HTTP {status}")
    if isinstance(body, str):
        print(f"    {C.DIM}{body[:200]}{C.RESET}")
    return False, []


def test_no_model(base: str) -> bool:
    status, _ = _request(
        base.rstrip("/") + CHAT_PATH, {"messages": [{"role": "user", "content": "hi"}]}
    )
    if status in (400, 404, 422):
        print(f"  {ok('no-model → error')}  HTTP {status} (correct)")
        return True
    print(f"  {warn('no-model → error')}  HTTP {status} (expected 400/404/422)")
    return False


def test_chat(base: str, model: str, verbose: bool = False) -> bool:
    url = base.rstrip("/") + CHAT_PATH
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": DEFAULT_PROMPT}],
        "max_tokens": 128,
    }
    t0 = time.monotonic()
    status, body = _request(url, payload)
    elapsed = time.monotonic() - t0

    if status == 200 and isinstance(body, dict):
        choice = body["choices"][0]
        content = (choice["message"].get("content") or "").strip()
        usage = body.get("usage", {})
        total = usage.get("total_tokens", "?")
        finish = choice.get("finish_reason", "")

        print(f"  {ok('chat')}  [{elapsed:.2f}s | {total} tokens | finish: {finish}]")
        # Always print the actual response text
        if content:
            for line in content.splitlines():
                print(f"      {C.MAGENTA}>{C.RESET} {line}")
        else:
            print(f"      {C.YELLOW}(empty content){C.RESET}")

        if verbose:
            print(f"\n    {C.DIM}--- full JSON ---")
            print(json.dumps(body, indent=2))
            print(f"---{C.RESET}")
        return True

    print(f"  {fail('chat')}  HTTP {status}")
    if isinstance(body, dict):
        err = body.get("message") or body.get("error") or body
        print(f"    {C.RED}{str(err)[:300]}{C.RESET}")
    else:
        print(f"    {C.RED}{str(body)[:300]}{C.RESET}")
    return False


def test_chat_stream(base: str, model: str) -> bool:
    url = base.rstrip("/") + CHAT_PATH
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": DEFAULT_PROMPT}],
        "max_tokens": 128,
    }
    t0 = time.monotonic()
    status, chunks = _stream_request(url, payload)
    elapsed = time.monotonic() - t0

    if status == 200:
        content = "".join(chunks).strip()
        print(f"  {ok('stream')}  [{elapsed:.2f}s | {len(chunks)} chunks]")
        if content:
            for line in content.splitlines():
                print(f"      {C.MAGENTA}>{C.RESET} {line}")
        else:
            print(f"      {C.YELLOW}(empty content){C.RESET}")
        return True

    print(f"  {fail('stream')}  HTTP {status}  {chunks[:1]}")
    return False


# ---------------------------------------------------------------------------
# Node loading
# ---------------------------------------------------------------------------
def load_nodes(node_filter: str | None, all_nodes: bool) -> dict[str, str]:
    if not STATE_PATH.exists():
        print(fail(f"state.json not found at {STATE_PATH}"))
        sys.exit(1)
    with STATE_PATH.open() as f:
        state = json.load(f)

    nodes = {}
    for name, info in state.items():
        # Filter by --node or default list (unless --all)
        if node_filter:
            if name != node_filter:
                continue
        elif not all_nodes:
            if name not in DEFAULT_NODES:
                continue

        url = info.get("url")
        if not url:
            continue

        services = info.get("services", [])
        if "llm_proxy" not in services:
            print(warn(f"Skipping {name} — llm_proxy not in deployed services"))
            continue
        nodes[name] = url

    if not nodes:
        print(
            fail(
                "No matching nodes with llm_proxy found. Run 'make build && make deploy' first."
            )
        )
        sys.exit(1)
    return nodes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(args):
    nodes = load_nodes(args.node, args.all)
    results = {}

    for node_name, base_url in nodes.items():
        print(f"\n{hdr('━━━')} {hdr(node_name)}  {C.DIM}{base_url}{C.RESET}")
        passed, total = 0, 0

        total += 1
        if test_health(base_url):
            passed += 1

        total += 1
        ok_models, model_ids = test_models(base_url)
        if ok_models:
            passed += 1

        if model_ids and args.model not in model_ids:
            print(
                f"    {C.YELLOW}hint: '{args.model}' not in available models — chat test may fail{C.RESET}"
            )

        total += 1
        if test_no_model(base_url):
            passed += 1

        total += 1
        if args.stream:
            if test_chat_stream(base_url, args.model):
                passed += 1
        else:
            if test_chat(base_url, args.model, verbose=args.verbose):
                passed += 1

        results[node_name] = (passed, total)

    # Summary
    print(f"\n{hdr('━━━━━━━━━━━━━━━━━━━━━━━━')}")
    print(hdr("  RESULTS SUMMARY"))
    print(hdr("━━━━━━━━━━━━━━━━━━━━━━━━"))
    all_pass = True
    for node_name, (passed, total) in results.items():
        colour = C.GREEN if passed == total else (C.YELLOW if passed > 0 else C.RED)
        icon = "✓" if passed == total else ("!" if passed > 0 else "✗")
        print(
            f"  {colour}{icon}{C.RESET}  {node_name:<14}  {colour}{passed}/{total}{C.RESET}"
        )
        if passed < total:
            all_pass = False
    print()
    sys.exit(0 if all_pass else 1)


def main():
    # Check if LITELLM_MASTER_KEY is set
    if not LITELLM_MASTER_KEY:
        print(f"Warning: LITELLM_MASTER_KEY not set in .env file")
        print(f"  Add it to your .env: LITELLM_MASTER_KEY=sk-your-key-here")
    else:
        print(f"Using LITELLM_MASTER_KEY from .env (length: {len(LITELLM_MASTER_KEY)})")

    parser = argparse.ArgumentParser(
        description="Test the LiteLLM proxy on deployed HF Space nodes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--node", metavar="NAME", help="Test only this specific node (e.g. server-01)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=f"Test all nodes (default: only {DEFAULT_NODES})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model name to use in chat test (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--stream", action="store_true", help="Use SSE streaming mode for the chat test"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print full JSON response bodies"
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
