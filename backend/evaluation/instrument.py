"""
Instrumentation for the SpecForge pipeline (metrics M1-M4 and token usage).

It wraps functions in ai.py at run time, so ai.py itself is not changed:

- every generate_* module is tagged, so each LLM call knows its module
- call_ai() is wrapped to record whether the first attempt parsed (M3)
  and whether the call was a repair prompt (M4)
- raw_ai_request() is wrapped to time every HTTP round trip and to tell
  first attempts from the gateway's stricter retry
- extract_message_content() is wrapped to capture the token usage
  that the Groq API returns with every response
"""

import asyncio
import re
import time

import ai

MAX_RATE_LIMIT_WAITS = 30
NETWORK_WAIT_S = 15.0
NETWORK_MARKERS = ("Could not connect to Groq", "getaddrinfo failed", "timed out after")


RETRY_MARKER = "Generate the requested result again."
REPAIR_MARKERS = {
    "Analyze these software requirements:": "actor/use-case repair",
    "Generate exactly 6 Agile user stories": "user-story retry",
}

MODULE_FUNCTIONS = {
    "generate_requirements": "Requirement Analyzer",
    "generate_user_stories": "User Story Generator",
    "generate_uml": "UML Generator",
    "generate_database": "Database Designer",
    "generate_apis": "API Designer",
    "generate_structure": "Project Structure",
    "generate_documentation": "Documentation",
}


class Recorder:
    """Collects everything that happens during one generate_sdlc() run."""

    def __init__(self):
        self.module = "unknown"
        self.calls = []          # one entry per call_ai() invocation
        self.requests = []       # one entry per HTTP request to the model
        self.module_times = {}   # module -> seconds spent (rate-limit waits excluded)
        self.throttle_seconds = 0.0  # total time lost to HTTP 429 waits
        self._open_call = None
        self._last_usage = None

    def summary(self):
        main_calls = [c for c in self.calls if c["purpose"] == "main"]
        repair_calls = [c for c in self.calls if c["purpose"] != "main"]
        first_ok = [c for c in main_calls if c["first_attempt_ok"]]
        retries = [r for r in self.requests if r["kind"] == "retry"]

        def total(field):
            values = [r["usage"].get(field) for r in self.requests if r.get("usage")]
            values = [v for v in values if isinstance(v, (int, float))]
            return sum(values) if values else None

        return {
            "main_calls": len(main_calls),
            "first_attempt_ok": len(first_ok),
            "gateway_retries": len(retries),
            "repair_calls": len(repair_calls),
            "repair_kinds": [c["purpose"] for c in repair_calls],
            "http_requests": len(self.requests),
            "prompt_tokens": total("prompt_tokens"),
            "completion_tokens": total("completion_tokens"),
            "total_tokens": total("total_tokens"),
            "module_seconds": {k: round(v, 3) for k, v in self.module_times.items()},
            "rate_limit_waits": sum(r.get("rate_limit_waits", 0) for r in self.requests),
            "rate_limit_wait_s": round(self.throttle_seconds, 3),
        }


_recorder = None


def start_recording():
    global _recorder
    _recorder = Recorder()
    return _recorder


def stop_recording():
    global _recorder
    finished, _recorder = _recorder, None
    return finished


# ------------------------------------------------------------
# Wrappers
# ------------------------------------------------------------

_original = {}


def _wrap_module(function_name, label):
    original = getattr(ai, function_name)

    async def wrapper(*args, **kwargs):
        if _recorder is None:
            return await original(*args, **kwargs)
        previous = _recorder.module
        _recorder.module = label
        started = time.perf_counter()
        throttle_before = _recorder.throttle_seconds
        try:
            return await original(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - started) - (_recorder.throttle_seconds - throttle_before)
            _recorder.module_times[label] = _recorder.module_times.get(label, 0) + elapsed
            _recorder.module = previous

    return wrapper


def _purpose_of(prompt):
    for marker, purpose in REPAIR_MARKERS.items():
        if prompt.lstrip().startswith(marker):
            return purpose
    return "main"


async def _call_ai_wrapper(prompt, max_tokens=1600):
    if _recorder is None:
        return await _original["call_ai"](prompt, max_tokens)

    record = {
        "module": _recorder.module,
        "purpose": _purpose_of(prompt),
        "max_tokens": max_tokens,
        "http_requests": 0,
        "first_attempt_ok": False,
        "succeeded": False,
        "error": None,
        "raw_output": None,
    }
    outer = _recorder._open_call
    _recorder._open_call = record
    try:
        result = await _original["call_ai"](prompt, max_tokens)
        record["succeeded"] = True
        # call_ai returns after the first request only if it parsed.
        record["first_attempt_ok"] = record["http_requests"] == 1
        record["raw_output"] = result
        return result
    except Exception as error:
        record["error"] = str(error)[:500]
        raise
    finally:
        _recorder.calls.append(record)
        _recorder._open_call = outer


def _rate_limit_wait(error):
    """Seconds to wait if the error is a provider rate limit (HTTP 429), else None.
    Groq says e.g. 'Please try again in 4.6275s' or 'in 1m2.5s' or 'in 850ms'."""
    text = str(error)
    # A dropped internet connection on the evaluation machine is not a failure
    # of the pipeline either: wait and resend the same request.
    if any(marker in text for marker in NETWORK_MARKERS):
        return NETWORK_WAIT_S
    if "429" not in text and "rate_limit" not in text.lower():
        return None
    match = re.search(r"try again in\s+(?:(\d+)m)?\s*([\d.]+)(ms|s)", text)
    if not match:
        return 10.0
    minutes = int(match.group(1) or 0)
    value = float(match.group(2))
    seconds = value / 1000 if match.group(3) == "ms" else value
    return minutes * 60 + seconds + 1.0  # one second of safety margin


async def _raw_request_wrapper(prompt, max_tokens=1600):
    if _recorder is None:
        return await _original["raw_ai_request"](prompt, max_tokens)

    kind = "retry" if prompt.lstrip().startswith(RETRY_MARKER) else "first"
    entry = {
        "module": _recorder.module,
        "kind": kind,
        "max_tokens": max_tokens,
        "seconds": None,
        "usage": None,
        "error": None,
        "rate_limit_waits": 0,
        "rate_limit_wait_s": 0.0,
    }
    if _recorder._open_call is not None:
        _recorder._open_call["http_requests"] += 1

    try:
        # A 429 is a quota limit of the free API tier, not a failure of the
        # pipeline: wait as instructed and resend the SAME request. The wait
        # is recorded separately and excluded from all latency figures, and
        # it never triggers the gateway's stricter retry.
        for _attempt in range(MAX_RATE_LIMIT_WAITS + 1):
            _recorder._last_usage = None
            started = time.perf_counter()
            try:
                return await _original["raw_ai_request"](prompt, max_tokens)
            except Exception as error:
                wait = _rate_limit_wait(error)
                if wait is None or _attempt == MAX_RATE_LIMIT_WAITS:
                    entry["error"] = str(error)[:300]
                    raise
                reason = "network error" if wait == NETWORK_WAIT_S else "rate limit reached"
                print(f"[evaluation] {reason}; waiting {wait:.1f} s (excluded from latency)")
                entry["rate_limit_waits"] += 1
                entry["rate_limit_wait_s"] += wait
                _recorder.throttle_seconds += wait + (time.perf_counter() - started)
                await asyncio.sleep(wait)
    finally:
        entry["seconds"] = round(time.perf_counter() - started, 3)
        entry["usage"] = _recorder._last_usage
        entry["rate_limit_wait_s"] = round(entry["rate_limit_wait_s"], 3)
        _recorder.requests.append(entry)


def _extract_wrapper(data):
    if _recorder is not None and isinstance(data, dict):
        usage = data.get("usage")
        if isinstance(usage, dict):
            _recorder._last_usage = {
                k: usage.get(k)
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
    return _original["extract_message_content"](data)


def install():
    """Patch ai.py functions once. Safe to call more than once."""
    if _original:
        return

    _original["call_ai"] = ai.call_ai
    _original["raw_ai_request"] = ai.raw_ai_request
    _original["extract_message_content"] = ai.extract_message_content

    ai.call_ai = _call_ai_wrapper
    ai.raw_ai_request = _raw_request_wrapper
    ai.extract_message_content = _extract_wrapper

    for function_name, label in MODULE_FUNCTIONS.items():
        setattr(ai, function_name, _wrap_module(function_name, label))
