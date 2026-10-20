#!/usr/bin/env python3
"""Monkey-patch adapter: makes the existing llm_judge.py work with an
OpenAI-compatible API instead of native Anthropic.

This module patches the `call_anthropic` function in llm_judge to route
through an OpenAI-compatible endpoint using streaming, using JUDGE_API_KEY,
JUDGE_BASE_URL, and JUDGE_MODEL from the environment.

Usage:
    Set JUDGE_API_KEY, JUDGE_BASE_URL, JUDGE_MODEL in the environment,
    then run this script with the same arguments as llm_judge.py:

    python judge_adapter.py --agent-output /home/agent/results/ \
                            --rubric /tests/rubric.json \
                            --result-file /tmp/eval/llm_judge.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import importlib.util
from pathlib import Path

import requests


def _int_env(key: str, default: int) -> int:
    """int() an env var, but treat missing OR empty/whitespace/invalid as default.
    (tmux panes may pass through vars as empty strings, which int('') would crash on.)"""
    v = (os.environ.get(key) or "").strip()
    try:
        return int(v) if v else default
    except ValueError:
        return default


def _judge_endpoints() -> list[dict]:
    """Primary + optional fallback judge endpoints, from env.
      primary : JUDGE_BASE_URL      / JUDGE_API_KEY      / JUDGE_MODEL
      fallback: JUDGE_BASE_URL_FALLBACK / JUDGE_API_KEY_FALLBACK / JUDGE_MODEL_FALLBACK
    """
    eps = []
    pk = os.environ.get("JUDGE_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    pb = os.environ.get("JUDGE_BASE_URL", "")
    pm = os.environ.get("JUDGE_MODEL", "")
    if pb and pk and pm:
        eps.append({"tag": "primary", "base_url": pb, "api_key": pk, "model": pm})
    fk = os.environ.get("JUDGE_API_KEY_FALLBACK", "")
    fb = os.environ.get("JUDGE_BASE_URL_FALLBACK", "")
    fm = os.environ.get("JUDGE_MODEL_FALLBACK", pm)
    if fb and fk and fm:
        eps.append({"tag": "fallback", "base_url": fb, "api_key": fk, "model": fm})
    if not eps:
        raise RuntimeError("No judge endpoint configured (need JUDGE_BASE_URL/JUDGE_API_KEY/JUDGE_MODEL)")
    return eps


def _stream_once(ep: dict, messages_content: list, events: list, timeout: int, stall: int) -> tuple:
    """One streaming call against a single endpoint. Enforces a hard wall-clock
    deadline (timeout) and a stall guard (abort if no content for `stall` s)."""
    url = f"{ep['base_url'].rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {ep['api_key']}", "Content-Type": "application/json"}
    payload = {
        "model": ep["model"],
        "messages": [{"role": "user", "content": messages_content}],
        "max_tokens": _int_env("JUDGE_MAX_TOKENS", 32000),
        "temperature": 0.0,
        "stream": True,
    }
    start = time.time()
    last = start
    resp = requests.post(url, headers=headers, json=payload, timeout=(15, stall), stream=True)
    resp.raise_for_status()
    chunks, finish_reason = [], None
    try:
        for line in resp.iter_lines(decode_unicode=True):
            now = time.time()
            if now - start > timeout:
                raise TimeoutError(f"judge exceeded {timeout}s wall-clock")
            if now - last > stall:
                raise TimeoutError(f"judge stalled >{stall}s with no content")
            if not line or not line.startswith("data: "):
                continue
            data_str = line[len("data: "):]
            if data_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or [{}]
            delta = choices[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                chunks.append(content)
                last = time.time()
            fr = choices[0].get("finish_reason")
            if fr:
                finish_reason = fr
    finally:
        resp.close()
    text = "".join(chunks)
    if not text:
        raise RuntimeError("streaming response returned empty content")
    stop_reason = "max_tokens" if finish_reason == "length" else "end_turn"
    events.append(f"[{ep['tag']}:{ep['model']}] judged in {time.time()-start:.0f}s ({len(text)} chars)")
    return text, stop_reason


def openai_compatible_call(prompt: str, figures: list[dict], events: list[str]) -> tuple:
    """Drop-in replacement for call_anthropic. Tries the primary judge endpoint,
    falls back to the secondary one, retrying the whole set up to JUDGE_MAX_RETRIES
    rounds. Per-attempt hard timeout JUDGE_TIMEOUT (default 1200s) with a stall
    guard JUDGE_STALL_SECS (default 240s)."""
    eps = _judge_endpoints()
    events.append("Judge endpoints: " + ", ".join(f"{e['tag']}={e['model']}@{e['base_url']}" for e in eps))

    messages_content = [{"type": "text", "text": prompt}]
    for fig in figures:
        if fig.get("type") == "image" and fig.get("source", {}).get("type") == "base64":
            messages_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{fig['source'].get('media_type', 'image/png')};base64,{fig['source']['data']}"
                },
            })

    retries = _int_env("JUDGE_MAX_RETRIES", 5)
    timeout = _int_env("JUDGE_TIMEOUT", 1200)
    stall = _int_env("JUDGE_STALL_SECS", 240)

    last_err = None
    for attempt in range(retries):
        for ep in eps:
            try:
                return _stream_once(ep, messages_content, events, timeout, stall)
            except Exception as e:
                last_err = e
                events.append(f"Judge [{ep['tag']}] round {attempt+1}/{retries} failed: {e}")
        wait = min(2 ** attempt, 30)
        time.sleep(wait)
    raise RuntimeError(f"Judge failed after {retries} rounds over {len(eps)} endpoint(s): {last_err}")


def patch_and_run(llm_judge_path: str, argv: list[str]):
    """Load llm_judge.py, patch call_anthropic, and run its main."""
    spec = importlib.util.spec_from_file_location("llm_judge", llm_judge_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["llm_judge"] = mod

    os.environ.setdefault("ANTHROPIC_API_KEY", os.environ.get("JUDGE_API_KEY", "dummy"))

    spec.loader.exec_module(mod)

    judge_model = os.environ.get("JUDGE_MODEL", "")
    if judge_model:
        mod.JUDGE_MODEL = judge_model
        print(f"[judge_adapter] Using judge model: {judge_model} (streaming)")

    mod.call_anthropic = openai_compatible_call

    old_argv = sys.argv
    sys.argv = [llm_judge_path] + argv
    try:
        mod.main()
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: judge_adapter.py <path-to-llm_judge.py> [llm_judge args...]")
        sys.exit(1)

    llm_judge_path = sys.argv[1]
    patch_and_run(llm_judge_path, sys.argv[2:])
