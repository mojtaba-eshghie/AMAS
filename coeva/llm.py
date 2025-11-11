from __future__ import annotations
from typing import Any
import json
from datetime import datetime

from .schemas import DiffPatch, TxPlan, TxCall, Finding
from . import config
from .logging_utils import get_logger, preview, write_text

log_http = get_logger("coeva.http", config.LOG_LEVEL)
llog     = get_logger("coeva.llm",  config.LOG_LEVEL)

def _chat_completion(system: str, user: str, *, expect_json: bool = False) -> str:
    import requests
    url = config.BASE_URL.rstrip('/') + '/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {config.API_KEY}',
        'Content-Type': 'application/json',
    }

    base = {
        'model': config.MODEL,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
    }

    variants = []

    # A) legacy tokens (+ optional temperature) (+ optional response_format)
    v = dict(base)
    v['max_tokens'] = 1024
    if getattr(config, 'TEMPERATURE', None) is not None:
        v['temperature'] = config.TEMPERATURE
    if expect_json:
        v['response_format'] = {'type': 'json_object'}
    variants.append(("A:max_tokens", v))

    # B) modern tokens (+ optional temperature) (+ optional response_format)
    v = dict(base)
    v['max_completion_tokens'] = 1024
    if getattr(config, 'TEMPERATURE', None) is not None:
        v['temperature'] = config.TEMPERATURE
    if expect_json:
        v['response_format'] = {'type': 'json_object'}
    variants.append(("B:max_completion_tokens", v))

    # C) modern tokens, no temp (keep response_format if expect_json)
    v = dict(base)
    v['max_completion_tokens'] = 1024
    if expect_json:
        v['response_format'] = {'type': 'json_object'}
    variants.append(("C:no-temp", v))

    # D) bare minimum (drop response_format too)
    variants.append(("D:bare", dict(base)))

    last_err = None
    for tag, payload in variants:
        if getattr(config, 'LOG_HTTP', False):
            log_http.debug(f"→ POST {url} tag={tag} model={config.MODEL} "
                           f"msg_len={sum(len(m['content']) for m in payload['messages'])}")

        resp = requests.post(url, headers=headers, json=payload, timeout=config.TIMEOUT)
        if resp.status_code < 400:
            data = resp.json()
            content = data['choices'][0]['message']['content']
            if getattr(config, 'LOG_HTTP', False):
                log_http.debug(f"← {resp.status_code} tag={tag} "
                               f"content_preview={preview(content, getattr(config, 'LOG_PREVIEW_CHARS', 240))}")
            return content

        # Error handling / fallback logic
        try:
            err = resp.json()
            msg = (err.get('error', {}) or {}).get('message', '')
        except Exception:
            err, msg = {'raw': resp.text}, resp.text
        last_err = (resp.status_code, err)

        # If temperature unsupported: drop and retry immediately
        if 'temperature' in msg and 'unsupported' in msg.lower():
            if 'temperature' in payload:
                payload = {k: v for k, v in payload.items() if k != 'temperature'}
                if getattr(config, 'LOG_HTTP', False):
                    log_http.debug(f"retry without temperature for tag={tag}")
                resp2 = requests.post(url, headers=headers, json=payload, timeout=config.TIMEOUT)
                if resp2.status_code < 400:
                    data = resp2.json()
                    return data['choices'][0]['message']['content']
                try:
                    err = resp2.json()
                except Exception:
                    err = {'raw': resp2.text}
                last_err = (resp2.status_code, err)
                continue

        # If max_tokens unsupported: let loop try next variant
        if 'max_tokens' in msg and 'max_completion_tokens' in msg.lower():
            continue

        # If response_format is unsupported, drop it and continue
        if 'response_format' in msg and 'unsupported' in msg.lower():
            continue

        # Otherwise surface the error now
        raise RuntimeError(f"LLM HTTP {resp.status_code} at {url}\nModel={config.MODEL}\nBody={err}")

    code, body = last_err if last_err else (None, None)
    raise RuntimeError(f"LLM request failed after fallbacks. Last error={code} Body={body}")

class LLM:
    def __init__(self, provider: str | None = None):
        self.provider = provider or config.PROVIDER

    def generate(self, role: str, strategy_name: str, system_prompt: str, user_prompt: str) -> Any:
        if self.provider == 'stub':
            # Deterministic stubs
            if role == 'injector':
                diff = (f'*** Begin Patch\n*** Update File: contracts/Example.sol\n@@\n'
                        f'- require(amount > 0);\n'
                        f'+ require(amount > 0 && amount <= maxDeposit[msg.sender]); // {strategy_name}\n'
                        f'*** End Patch\n')
                return DiffPatch(strategy=strategy_name, diff_text=diff, meta={'note': 'stub'})
            if role == 'exploiter':
                seq = [TxCall(to='Target', function='sink', args=['1000'])]
                return TxPlan(strategy=strategy_name, sequence=seq, rationale='stub')
            if role == 'detector':
                return Finding(strategy=strategy_name, type='Unchecked slippage',
                               location='Router.sol:212', invariant='amountOut >= minOut', confidence=0.7)
            if role == 'patcher':
                diff = (f'*** Begin Patch\n*** Update File: contracts/Example.sol\n@@\n'
                        f'- // TODO\n+ require(amountOut >= minOut, "slippage"); // {strategy_name}\n'
                        f'*** End Patch\n')
                return DiffPatch(strategy=strategy_name, diff_text=diff, meta={'note': 'stub'})
            raise ValueError(f'Unknown role: {role}')

        # Real request
        expect_json = role in ('exploiter', 'detector')
        content = _chat_completion(system_prompt, user_prompt, expect_json=expect_json)

        # Save raw I/O (optional)
        if getattr(config, 'SAVE_RAW', False):
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            raw_dir = getattr(config, 'RAW_DIR', 'logs/raw')
            base = f"{raw_dir}/{role}/{ts}_{strategy_name}"
            write_text(base + "_system.txt", system_prompt)
            write_text(base + "_user.txt", user_prompt)
            write_text(base + "_response.txt", content)

        # Guard: empty content — retry once with a nudge
        if not content or not content.strip():
            llog.warning(f"{role}:{strategy_name} empty content; retrying once with nudge")
            nudged = user_prompt + "\n\nIf you returned nothing, output a minimal valid result NOW."
            content = _chat_completion(system_prompt, nudged, expect_json=expect_json)
            if not content or not content.strip():
                if role in ('injector', 'patcher'):
                    content = "*** Begin Patch\n*** End Patch\n"
                else:
                    content = "{}"

        if role == 'exploiter':
            # Expect JSON; fall back gracefully
            try:
                obj = json.loads(content)
                seq = obj.get('sequence', [])
                if not isinstance(seq, list):
                    seq = []
                calls = []
                for c in seq:
                    try:
                        calls.append(TxCall(**c))
                    except Exception:
                        pass
                return TxPlan(strategy=strategy_name, sequence=calls, rationale=obj.get('rationale', ''))
            except Exception:
                return TxPlan(strategy=strategy_name, sequence=[], rationale=content)

        if role == 'detector':
            # Accept {"finding": {...}} or flat JSON
            try:
                obj = json.loads(content)
                if isinstance(obj, dict) and 'finding' in obj and isinstance(obj['finding'], dict):
                    obj = obj['finding']
                return Finding(strategy=strategy_name,
                               type=obj.get('type', 'Unknown'),
                               location=obj.get('location', ''),
                               invariant=obj.get('invariant', ''),
                               confidence=float(obj.get('confidence', 0.5)))
            except Exception:
                return Finding(strategy=strategy_name, type='Free-form', location='',
                               invariant=(content or '')[:80], confidence=0.5)

        if role in ('injector', 'patcher'):
            # Treat raw text as a unified diff
            return DiffPatch(strategy=strategy_name, diff_text=content, meta={})

        raise ValueError(f'Unknown role: {role}')
