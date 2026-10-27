"""Nemotron client: OpenAI-compatible NVIDIA API with throttling, retries,
schema validation + repair, and a record/replay cache keyed by prompt hash."""
from __future__ import annotations

import hashlib
import os
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from .config import settings

log = logging.getLogger("unclaimed.llm")
T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """Raised when no live call is possible and the cache has no entry."""


@dataclass
class LLMMeta:
    model: str
    cache_hit: bool
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    attempts: int
    source: str  # live | cache | stub
    reasoning: str = ""  # the model's reasoning text, when it returns one


_sem = threading.BoundedSemaphore(max(1, settings.llm_concurrency))
_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(base_url=settings.nvidia_base_url, api_key=settings.nvidia_api_key, timeout=float(os.environ.get("LLM_TIMEOUT_S", "420")), max_retries=0)
    return _client


def _key(model: str, messages: list[dict], temperature: float, thinking: bool = True) -> str:
    payload = {"m": model, "msg": messages, "t": temperature}
    if not thinking:
        payload["think"] = False
    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _cache_path(key: str):
    return settings.cache_dir / f"{key}.json"


def _cache_get(key: str) -> dict | None:
    p = _cache_path(key)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _cache_put(key: str, record: dict) -> None:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(json.dumps(record, indent=1), encoding="utf-8")


def _raw_call(model: str, messages: list[dict], temperature: float, max_tokens: int, thinking: bool = True) -> dict:
    """One live call with exponential backoff on 429/5xx/timeouts."""
    if not settings.nvidia_api_key:
        raise LLMUnavailable("NVIDIA_API_KEY not set")
    delay = 2.0
    last: Exception | None = None
    for attempt in range(6):
        try:
            with _sem:
                t0 = time.time()
                extra = {} if thinking else {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
                r = _get_client().chat.completions.create(
                    model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, **extra
                )
            u = r.usage
            msg = r.choices[0].message
            extra_fields = msg.model_extra or {}
            return {
                "content": msg.content or "",
                "reasoning": extra_fields.get("reasoning_content") or extra_fields.get("reasoning") or "",
                "finish_reason": r.choices[0].finish_reason,
                "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
                "latency_s": round(time.time() - t0, 3),
            }
        except Exception as e:  # openai raises typed errors; retry the transient ones
            status = getattr(e, "status_code", None)
            transient = status in (429, 500, 502, 503, 504) or "timeout" in type(e).__name__.lower() or "connection" in type(e).__name__.lower()
            if status in (401, 403):
                raise LLMUnavailable(f"auth error {status}") from e
            if not transient:
                raise
            last = e
            log.warning("nemotron transient error %s (attempt %d), backing off %.0fs", status or type(e).__name__, attempt + 1, delay)
            time.sleep(delay)
            delay = min(delay * 2, 60)
    raise LLMUnavailable(f"retries exhausted: {last}")


def complete(model: str, messages: list[dict], temperature: float = 0.0, max_tokens: int = 4096,
             thinking: bool = True) -> tuple[str, LLMMeta]:
    key = _key(model, messages, temperature, thinking)
    cached = _cache_get(key)
    if cached is not None:
        # latency reported is the one measured on the original live call
        return cached["content"], LLMMeta(model, True, cached.get("latency_s", 0.0), cached["prompt_tokens"],
                                          cached["completion_tokens"], 1, "cache", cached.get("reasoning", ""))
    if settings.llm_mode != "live":
        raise LLMUnavailable(f"no cache entry ({settings.llm_mode} mode)")
    rec = _raw_call(model, messages, temperature, max_tokens, thinking)
    rec["model"] = model
    _cache_put(key, rec)
    return rec["content"], LLMMeta(model, False, rec["latency_s"], rec["prompt_tokens"], rec["completion_tokens"], 1, "live",
                                   rec.get("reasoning", ""))


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("no JSON found in model output")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def chat_json(
    model: str,
    system: str,
    user: str,
    schema: type[T],
    validate: Callable[[T], list[str]] | None = None,
    max_repairs: int = 2,
    max_tokens: int = 4096,
    thinking: bool = True,
) -> tuple[T, LLMMeta]:
    """Ask for JSON, validate against a pydantic schema (+ optional semantic
    checks), and run a repair loop of at most `max_repairs` retries."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    total_p = total_c = 0
    latency = 0.0
    all_cached = True
    for attempt in range(max_repairs + 1):
        content, meta = complete(model, messages, max_tokens=max_tokens, thinking=thinking)
        total_p += meta.prompt_tokens
        total_c += meta.completion_tokens
        latency += meta.latency_s
        all_cached &= meta.cache_hit
        try:
            obj = schema.model_validate(extract_json(content))
            errors = validate(obj) if validate else []
            if not errors:
                return obj, LLMMeta(model, all_cached, latency, total_p, total_c, attempt + 1,
                                    "cache" if all_cached else "live", meta.reasoning)
            problem = "; ".join(errors)
        except (ValueError, ValidationError) as e:
            problem = str(e)[:1500]
        log.info("repairing %s output (attempt %d): %s", schema.__name__, attempt + 1, problem[:200])
        messages = messages + [
            {"role": "assistant", "content": content},
            {"role": "user", "content": f"Your JSON was invalid: {problem}\nReturn ONLY the corrected JSON object."},
        ]
    raise ValueError(f"{schema.__name__}: invalid after {max_repairs} repairs: {problem}")


def available() -> bool:
    return bool(settings.nvidia_api_key) and settings.llm_mode == "live"
