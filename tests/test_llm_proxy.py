#!/usr/bin/env python3
"""
tests/test_llm_proxy.py

Test the LiteLLM proxy (/v1/) on all nodes listed in manifests/state.json.

Usage:
    uv run python tests/test_llm_proxy.py
    uv run python tests/test_llm_proxy.py --node server-03
    uv run python tests/test_llm_proxy.py --model openai/gpt-oss-120b
    uv run python tests/test_llm_proxy.py --stream
    uv run python tests/test_llm_proxy.py --verbose

LLM_KEYS format in .env for Groq:
    LLM_KEYS="groq:openai/gpt-oss-120b:gsk_xxxxxxxxxxxx"

Multiple keys (load-balanced):
    LLM_KEYS="groq:openai/gpt-oss-120b:gsk_key1,groq:openai/gpt-oss-120b:gsk_key2"
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT  = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "manifests" / "state.json"

CHAT_PATH   = "/v1/chat/completions"
MODELS_PATH = "/v1/models"
HEALTH_PATH = "/health"

DEFAULT_MODEL  = "openai/gpt-oss-120b"   # model_name as exposed by litellm (from LLM_KEYS)
DEFAULT_PROMPT = "Reply in exactly three words."
TIMEOUT = 10   # short — we have up to 6 nodes × 4 checks, don't want to hang


# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
class C:
    RESET = "\033[0m"; BOLD = "\033[1m"
    GREEN = "\033[92m"; RED = "\033[91m"
    YELLOW = "\033[93m"; CYAN = "\033[96m"; DIM = "\033[2m"

def ok(msg):   return f"{C.GREEN}✓{C.RESET} {msg}"
def fail(msg): return f"{C.RED}✗{C.RESET} {msg}"
def warn(msg): return f"{C.YELLOW}!{C.RESET} {msg}"
def hdr(msg):  return f"{C.BOLD}{C.CYAN}{msg}{C.RESET}"


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------
def _request(url: str, payload: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode() if payload else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode()
            try:    return resp.status, json.loads(body)
            except: return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:    return e.code, json.loads(body)
        except: return e.code, body
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
            for raw in resp:
                line = raw.decode().strip()
                if not line.startswith("data:"): continue
                s = line[5:].strip()
                if s == "[DONE]": break
                try:
                    delta = json.loads(s)["choices"][0]["delta"].get("content", "")
                    if delta: chunks.append(delta)
                except: pass
            return resp.status, chunks
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


def test_models(base: str, verbose: bool = False) -> tuple[bool, list[str]]:
    status, body = _request(base.rstrip("/") + MODELS_PATH)
    if status == 200 and isinstance(body, dict):
        ids = [m.get("id", "?") for m in body.get("data", [])]
        print(f"  {ok('models')}  {', '.join(ids) or '(none)'}")
        if verbose:
            print(f"    {C.DIM}{json.dumps(body, indent=2)[:400]}{C.RESET}")
        return True, ids
    print(f"  {fail('models')}  HTTP {status}")
    return False, []


def test_no_model(base: str) -> bool:
    status, _ = _request(base.rstrip("/") + CHAT_PATH,
                         {"messages": [{"role": "user", "content": "hi"}]})
    if status in (400, 422):
        print(f"  {ok('no-model → 400')}  HTTP {status} (correct)")
        return True
    print(f"  {warn('no-model → 400')}  HTTP {status} (expected 400/422)")
    return False


def test_chat(base: str, model: str, verbose: bool = False) -> bool:
    url = base.rstrip("/") + CHAT_PATH
    payload = {"model": model,
               "messages": [{"role": "user", "content": DEFAULT_PROMPT}],
               "max_tokens": 32}
    t0 = time.monotonic()
    status, body = _request(url, payload)
    elapsed = time.monotonic() - t0

    if status == 200 and isinstance(body, dict):
        content = body["choices"][0]["message"]["content"].strip()
        tokens  = body.get("usage", {}).get("total_tokens", "?")
        print(f"  {ok('chat')}  [{elapsed:.1f}s, {tokens} tok]  \"{content}\"")
        if verbose:
            print(f"    {C.DIM}{json.dumps(body, indent=2)[:600]}{C.RESET}")
        return True

    print(f"  {fail('chat')}  HTTP {status}")
    if isinstance(body, dict):
        err = body.get("message") or body.get("error") or body
        print(f"    {C.RED}{str(err)[:200]}{C.RESET}")
    else:
        print(f"    {C.RED}{str(body)[:200]}{C.RESET}")
    return False


def test_chat_stream(base: str, model: str) -> bool:
    url = base.rstrip("/") + CHAT_PATH
    payload = {"model": model,
               "messages": [{"role": "user", "content": DEFAULT_PROMPT}],
               "max_tokens": 32}
    t0 = time.monotonic()
    status, chunks = _stream_request(url, payload)
    elapsed = time.monotonic() - t0

    if status == 200:
        content = "".join(chunks).strip()
        print(f"  {ok('stream')}  [{elapsed:.1f}s, {len(chunks)} chunks]  \"{content}\"")
        return True
    print(f"  {fail('stream')}  HTTP {status}  {chunks[:1]}")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def load_nodes(node_filter: str | None) -> dict[str, str]:
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
        services = info.get("services", [])
        if "llm_proxy" not in services:
            print(warn(f"Skipping {name} — llm_proxy not in deployed services (need make build && make deploy)"))
            continue
        nodes[name] = url

    if not nodes:
        print(fail("No nodes with llm_proxy found in state.json. Run 'make build && make deploy' first."))
        sys.exit(1)
    return nodes


def run(args):
    nodes = load_nodes(args.node)
    results = {}

    for node_name, base_url in nodes.items():
        print(f"\n{hdr('━━━')} {hdr(node_name)}  {C.DIM}{base_url}{C.RESET}")
        passed = 0
        total  = 0

        total += 1
        if test_health(base_url): passed += 1

        total += 1
        ok_models, model_ids = test_models(base_url, verbose=args.verbose)
        if ok_models: passed += 1

        # Show a hint if the deployed model differs from what we'll test
        if model_ids and args.model not in model_ids:
            print(f"    {C.YELLOW}hint: available models are {model_ids}; "
                  f"testing with --model {args.model}{C.RESET}")

        total += 1
        if test_no_model(base_url): passed += 1

        total += 1
        if args.stream:
            if test_chat_stream(base_url, args.model): passed += 1
        else:
            if test_chat(base_url, args.model, verbose=args.verbose): passed += 1

        results[node_name] = (passed, total)

    # Summary
    print(f"\n{hdr('━━━━━━━━━━━━━━━━━━━━━━━━')}")
    print(hdr("  RESULTS SUMMARY"))
    print(hdr("━━━━━━━━━━━━━━━━━━━━━━━━"))
    all_pass = True
    for node_name, (passed, total) in results.items():
        colour = C.GREEN if passed == total else (C.YELLOW if passed > 0 else C.RED)
        icon   = "✓" if passed == total else ("!" if passed > 0 else "✗")
        print(f"  {colour}{icon}{C.RESET}  {node_name:<14}  {colour}{passed}/{total}{C.RESET}")
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
    parser.add_argument("--node",   metavar="NAME", help="Test only this node (e.g. server-03)")
    parser.add_argument("--model",  default=DEFAULT_MODEL,
                        help=f"Model name to test (default: {DEFAULT_MODEL})")
    parser.add_argument("--stream", action="store_true", help="Use SSE streaming mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print full JSON responses")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
