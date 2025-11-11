from __future__ import annotations
from typing import Any
import json, time, os
from requests.exceptions import ReadTimeout, ConnectionError
from .schemas import DiffPatch, TxPlan, TxCall, Finding
from . import config
from .logging_utils import get_logger, preview
from datetime import datetime

log_http = get_logger("coeva.http", config.LOG_LEVEL)
llog = get_logger("coeva.llm", config.LOG_LEVEL)



def _save_raw(role: str, strategy: str, kind: str, text: str) -> None:
    try:
        if not getattr(config, "SAVE_RAW", False):
            return
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        root = getattr(config, "RAW_DIR", "logs/raw")
        d = os.path.join(root, role, f"{ts}_{strategy}")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{kind}.txt"), "w", encoding="utf-8") as f:
            f.write(text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, indent=2))
    except Exception:
        pass

def _is_reasoning_model(name: str) -> bool:
    return "gpt-5" in name  # guard all GPT-5* variants

def _mk_payload(system: str, user: str, *, expect_json: bool, max_ct: int) -> dict:
    p = {
        "model": config.MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_completion_tokens": max_ct,
    }
    # Reasoning effort: many GPT-5 deployments accept this; if not, we fall back below.
    if _is_reasoning_model(config.MODEL) and config.REASONING_EFFORT != "omit":
        p["reasoning"] = {"effort": config.REASONING_EFFORT}
    # Only force response_format for JSON cases (text sometimes misbehaves if set).
    if expect_json:
        p["response_format"] = {"type": "json_object"}
    return p

def _post(url: str, headers: dict, payload: dict):
    import requests
    return requests.post(url, headers=headers, json=payload, timeout=config.TIMEOUT)

def _used_reasoning_tokens(data: dict) -> int:
    # Different backends expose this differently; be defensive.
    u = data.get("usage", {}) or {}
    details = u.get("completion_tokens_details", {}) or {}
    return int(details.get("reasoning_tokens", 0))

def _finish_reason(data: dict) -> str:
    try:
        return data["choices"][0].get("finish_reason") or ""
    except Exception:
        return ""

def _chat_completion(system: str, user: str, *, expect_json: bool = False) -> str:
    url = config.BASE_URL.rstrip("/") + "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {config.API_KEY}", "Content-Type": "application/json"}

    # Start with a healthy budget; auto-escalate if we detect reasoning-exhaustion.
    max_ct = max(256, config.MAX_COMPLETION_TOKENS)
    ceiling = max_ct if config.MAX_COMPLETION_CEILING < max_ct else config.MAX_COMPLETION_CEILING

    attempts = 0
    while True:
        attempts += 1
        payload = _mk_payload(system, user, expect_json=expect_json, max_ct=max_ct)

        # Send
        try:
            if config.LOG_HTTP:
                log_http.debug(f"→ POST {url} model={config.MODEL} max_ct={max_ct} "
                               f"msg_len={sum(len(m['content']) for m in payload['messages'])} "
                               f"try={attempts}")
            resp = _post(url, headers, payload)
        except (ReadTimeout, ConnectionError) as e:
            if attempts < 3:
                time.sleep(1.5 ** attempts)
                continue
            raise

        # Handle non-OK HTTP
        if resp.status_code >= 400:
            # Graceful fallbacks for unsupported params on some gateways:
            try:
                err = resp.json()
                msg = (err.get("error") or {}).get("message", "")
            except Exception:
                err, msg = {"raw": resp.text}, resp.text

            # Remove unsupported 'reasoning' if needed and retry once
            if "reasoning" in msg.lower() and attempts < 3:
                llog.warning("server rejected 'reasoning' param; retrying without it")
                # strip and retry
                user = user + "\n\n[no_reasoning]"
                config.REASONING_EFFORT = "omit"
                continue

            # Switch max_tokens->max_completion_tokens is already handled; other params omitted
            raise RuntimeError(f"LLM HTTP {resp.status_code} at {url}\nModel={config.MODEL}\nBody={err}")

        data = resp.json()
        finish = _finish_reason(data)
        content = (data.get("choices", [{}])[0].get("message") or {}).get("content", "") or ""
        r_tokens = _used_reasoning_tokens(data)

        if config.LOG_HTTP:
            # Show why it might be empty
            up = data.get("usage", {})
            log_http.debug(f"← 200 finish={finish} used={{prompt:{up.get('prompt_tokens')}, "
                           f"completion:{up.get('completion_tokens')}, reasoning:{r_tokens}}} "
                           f"preview={preview(content, config.LOG_PREVIEW_CHARS)}")

        # If we got content, return it.
        if content.strip():
            return content

        # No content. If we appear to have burned the budget on reasoning → escalate and retry.
        if _is_reasoning_model(config.MODEL) and (finish == "length" or r_tokens > 0):
            new_max = min(ceiling, max_ct * 2)
            if new_max > max_ct:
                llog.warning(f"empty content (reasoning={r_tokens}, finish={finish}); "
                             f"escalating max_completion_tokens {max_ct} → {new_max} and retrying")
                max_ct = new_max
                # Also nudge: ask for minimal valid output now.
                user = user + "\n\nIf you returned nothing, output a minimal valid result NOW."
                continue

        # Final fallback: return a minimal syntactically-valid stub so pipelines don’t break.
        return content  # may be ""

class LLM:
    def __init__(self, provider: str | None = None):
        self.provider = provider or config.PROVIDER

    def generate(self, role: str, strategy_name: str, system_prompt: str, user_prompt: str) -> Any:
        if self.provider == 'stub':
            # Deterministic stubs
            if role == 'injector':
                diff = (
                    '*** Begin Patch\n*** Update File: contracts/Example.sol\n@@\n'
                    '- require(amountOut >= minOut, "slippage");\n'
                    '+ require(amountOut >  minOut, "slippage"); // weakened\n'
                    '*** End Patch\n'
                )
                return DiffPatch(strategy=strategy_name, diff_text=diff, meta={'note': 'stub'})
            if role == 'exploiter':
                seq = [TxCall(to='Target', function='sink', args=['1000'])]
                return TxPlan(strategy=strategy_name, sequence=seq, rationale='stub')
            if role == 'detector':
                return Finding(strategy=strategy_name, type='Unchecked slippage',
                               location='Router.sol:212', invariant='amountOut >= minOut', confidence=0.7)
            if role == 'patcher':
                diff = (
                    '*** Begin Patch\n*** Update File: contracts/Example.sol\n@@\n'
                    '- // TODO\n'
                    '+ require(amountOut >= minOut, "slippage"); // strengthened\n'
                    '*** End Patch\n'
                )
                return DiffPatch(strategy=strategy_name, diff_text=diff, meta={'note': 'stub'})
            raise ValueError(f'Unknown role: {role}')

        # Real request
        expect_json = role in ('exploiter', 'detector')

        # raw I/O (only if enabled via env)
        _save_raw(role, strategy_name, "system", system_prompt)
        _save_raw(role, strategy_name, "user", user_prompt)

        content = _chat_completion(system_prompt, user_prompt, expect_json=expect_json)

        _save_raw(role, strategy_name, "response", content or "")

        if role == 'exploiter':
            try:
                obj = json.loads(content or "{}")
                calls = [TxCall(**c) for c in obj.get('sequence', [])]
                return TxPlan(strategy=strategy_name, sequence=calls, rationale=obj.get('rationale', ''))
            except Exception:
                return TxPlan(strategy=strategy_name, sequence=[], rationale=(content or ""))

        if role == 'detector':
            try:
                obj = json.loads(content or "{}")
                return Finding(
                    strategy=strategy_name,
                    type=obj.get('type', 'Unknown'),
                    location=obj.get('location', ''),
                    invariant=obj.get('invariant', ''),
                    confidence=float(obj.get('confidence', 0.5)),
                )
            except Exception:
                return Finding(
                    strategy=strategy_name,
                    type='Free-form',
                    location='',
                    invariant=(content or '')[:80],
                    confidence=0.5,
                )

        # injector / patcher expect a unified diff (text)
        if not content or not content.strip():
            # keep loop alive with a minimal syntactically-valid patch
            content = (
                "*** Begin Patch\n*** Update File: contracts/Example.sol\n@@\n"
                "- \n+ // no-op to keep loop alive\n"
                "*** End Patch\n"
            )
        return DiffPatch(strategy=strategy_name, diff_text=content, meta={})