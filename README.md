# Cat&Mouse

Minimal, *weight-free* multi-agent skeleton for adversarial smart-contract workflows using **Portfolio + Bandits**.
Each role (Injector, Exploiter, Detector, Patcher) is just an **LLM prompt strategy**. We adapt **online** by picking the best strategy via a **multi-armed bandit**—no finetuning, no chat history, no guardrails.

---

## Goal

Build a practical starting point for your “Cat & Mouse” ecosystem **without** heavy training loops:

* **No SFT/RL** to start.
* **No conversation history**; each step is single-turn.
* **Online adaptation via bandits** selecting among a small **portfolio of prompts** per role.
* Pluggable **programmatic oracles** (compile/tests/anvil/specs) returning a numeric reward in `[0,1]`.

---

## What we decided to build

**Option 1: Portfolio + Bandits**

* For each agent/role we keep a **portfolio** of prompt templates (the “arms”).
* After each trial, a **reward** is computed by your oracles (e.g., exploit success, patch validity).
* A **bandit policy** (UCB1 / Thompson / EXP3) updates beliefs and selects the next arm.
* **No model weights** are updated; adaptation happens at inference time.

---

## Current state

✅ **Implemented**

* **Bandit policies:** `UCB1`, `ThompsonBernoulli`, `EXP3`
* **Strategy portfolios:** initial arms for `injector`, `exploiter`, `detector`, `patcher`
* **LLM providers:** `stub` (deterministic) and `openai` (any OpenAI-compatible `/v1/chat/completions`)
* **Controller:** select → generate → score → update (with JSONL logging)
* **Schemas:** `DiffPatch`, `TxPlan`, `Finding`
* **Logging & Forensics:** JSONL per role, optional raw I/O dumps, on-disk artifacts (`patch.diff`, `txplan.json`, `finding.json`)

🧪 **Demos**

* `scripts/run_demo.py` → **stub LLM** + toy oracles
* `scripts/run_openai_demo.py` → **real LLM** path if configured

🧰 **Your TODO**

* Replace toy functions in `coeva/oracles.py` with your **real** harness (compile/tests/anvil/specs, non-vacuity, etc.)

---

## Folder structure

```
coeva-lite/
├─ coeva/
│  ├─ bandits.py        # UCB1, Thompson, EXP3
│  ├─ strategies.py     # Prompt portfolios for each role
│  ├─ llm.py            # Stub + OpenAI-compatible client (JSON/text modes, retries)
│  ├─ controller.py     # Orchestrates select→generate→score→update (+ JSONL logging)
│  ├─ oracles.py        # <== Replace with real compile/test/anvil/spec rewarders
│  ├─ schemas.py        # DiffPatch, TxPlan, Finding
│  └─ config.py         # ENV config (provider/base_url/model/timeout/logging)
├─ scripts/
│  ├─ run_demo.py       # Stub LLM + toy oracles (quick smoke test)
│  └─ run_openai_demo.py# Real LLM path if configured
└─ tests/
   └─ test_bandits.py   # bandit smoke tests
```

---

## Quickstart

### 1) Stub demo (no external model)

```bash
python3 scripts/run_demo.py
```

You’ll see each role pick strategies and rewards update over time.
*(Uses stub LLM + toy oracles; numbers are illustrative.)*

---

## Running with a real LLM (OpenAI-compatible)

> Works with OpenAI, vLLM, LM Studio, Together, etc.—anything that speaks `/v1/chat/completions`.

### A) Environment variables

```bash
# Provider + endpoint + model
export COEVA_LLM_PROVIDER=openai
export COEVA_OPENAI_BASE_URL=https://api.openai.com
export COEVA_OPENAI_MODEL=gpt-4o-mini           # or your local model name
export OPENAI_API_KEY=sk-...                    # or token for your local proxy

# Logging (optional but recommended)
export COEVA_LOG=1
export COEVA_LOG_DIR=logs
export COEVA_LOG_LEVEL=DEBUG
export COEVA_LOG_PROMPTS=1
export COEVA_LOG_ARTIFACTS=1
export COEVA_LOG_HTTP=1
export COEVA_LOG_PREVIEW=400

# Save raw I/O and artifacts to disk
export COEVA_SAVE_RAW=1
export COEVA_RAW_DIR=logs/raw
export COEVA_ARTIFACTS_DIR=artifacts

# Some models reject temperature; omit to avoid 400s
export COEVA_TEMPERATURE=omit
```

### B) Use a **SAFE baseline** Solidity file

Injector/Patcher operate on unified diffs. Use a baseline that **already enforces** the property so:

* **Injector** can weaken it,
* **Patcher** can restore it.

Place this into your demo **context** (the `file_text` used by the injector/patcher prompts):

```solidity
// contracts/Example.sol
// Baseline SAFE version (enforces amountOut >= minOut)
pragma solidity ^0.8.20;

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
}

contract Router {
    IERC20 public tokenIn;
    IERC20 public tokenOut;

    constructor(IERC20 _in, IERC20 _out) {
        tokenIn = _in;
        tokenOut = _out;
    }

    function getQuote(uint256 amountIn) public view returns (uint256) {
        return (amountIn * 98) / 100; // toy quote: 2% fee
    }

    function swap(uint256 amountIn, uint256 minOut) external returns (uint256 amountOut) {
        require(amountIn > 0, "zero-in");
        amountOut = getQuote(amountIn);
        require(amountOut >= minOut, "slippage"); // <-- anchor for injector/patcher
        tokenIn.transferFrom(msg.sender, address(this), amountIn);
        tokenOut.transfer(msg.sender, amountOut);
    }
}
```

> We’ve also added a **one-shot diff example** inside `coeva/strategies.py` system prompts for injector/patcher so models reliably output:
>
> ```
> *** Begin Patch
> *** Update File: contracts/Example.sol
> @@
> - require(amountOut >= minOut, "slippage");
> + require(amountOut >  minOut, "slippage"); // weakened/strengthened
> *** End Patch
> ```

### C) Run

```bash
PYTHONPATH=. python3 scripts/run_openai_demo.py
```

You should see, per role:

* strategy selection (explore/exploit),
* prompts (DEBUG preview),
* HTTP variant chosen (max_tokens vs max_completion_tokens),
* produced artifact preview,
* reward + updated bandit means.

Artifacts & logs are saved to:

```
artifacts/<role>/t0000_<strategy>/patch.diff | txplan.json | finding.json
logs/<role>.jsonl
logs/raw/<role>/<timestamp>_<strategy>_{system,user,response}.txt
```

---

## How it works (1 page)

**Per step per role:**

1. **Select** an arm with a bandit policy (e.g., UCB1).
2. **Generate** an artifact via LLM + strategy template:

   * Injector/Patcher → **unified diff** (text)
   * Exploiter/Detector → **JSON** (`TxPlan` / `Finding`)
3. **Score** with your oracle → reward ∈ `[0,1]`.
4. **Update** bandit stats; log JSONL and save artifacts.

**Design choices**

* **No history:** single-turn calls; “state” lives in bandit counts/means and your logs.
* **No training:** pure test-time adaptation.
* **Rewards first:** oracles are the source of truth (compile/tests/spec/anvil).
* **Clip/normalize** rewards to `[0,1]` for stable bandits.

---

## Wiring real oracles (edit `coeva/oracles.py`)

* `evaluate_injector(diff)`
  Build/compile/apply patch → run tests/specs → measure **Δ exploitability**.
* `evaluate_exploiter(plan)`
  Execute on anvil; success iff invariant is violated; penalize gas/tx_count.
* `evaluate_detector(finding)`
  Severity-weighted precision/recall vs ground-truth or runtime asserts.
* `evaluate_patcher(diff)`
  Apply patch; exploit must fail; tests/specs pass; non-vacuous; small AST delta.

Return a `(reward: float ∈ [0,1], feedback: str)`.

---

## Configuration reference

* `COEVA_LLM_PROVIDER`: `stub` (default) or `openai`
* `COEVA_OPENAI_BASE_URL`: e.g., `https://api.openai.com`
* `COEVA_OPENAI_MODEL`: e.g., `gpt-4o-mini`, `llama-3-8b-instruct`
* `OPENAI_API_KEY`: API key (or token for local proxies)
* `COEVA_LLM_TIMEOUT`: seconds (default `60`)
* `COEVA_TEMPERATURE`: `omit` to avoid unsupported param on some models
* Logging:

  * `COEVA_LOG` (`1`), `COEVA_LOG_DIR`, `COEVA_LOG_LEVEL`
  * `COEVA_LOG_PROMPTS` (`1`) to log prompts, `COEVA_LOG_ARTIFACTS` (`1`) to log artifacts
  * `COEVA_LOG_HTTP` (`1`) to show API variant decisions
  * `COEVA_LOG_PREVIEW` to limit console previews
* Forensics:

  * `COEVA_SAVE_RAW` (`1`) + `COEVA_RAW_DIR`
  * `COEVA_ARTIFACTS_DIR` (default `artifacts`)

---

## Troubleshooting

* **Empty output for injector/patcher**
  Confirm your `file_text` contains the anchors (e.g., `require(amountOut >= minOut, "slippage");`).
  We now force **text** `response_format` for these roles and retry once; final fallback emits a minimal no-op diff to keep the loop alive.
* **400: unsupported `max_tokens`**
  We automatically retry with `max_completion_tokens`.
* **400: unsupported `temperature`**
  Set `COEVA_TEMPERATURE=omit` (already handled).
* **Model returning JSON for diffs**
  We’ll extract `{"diff": "...patch..."}` if present; otherwise treat raw text as a unified diff.

---

## Extending the portfolio (`coeva/strategies.py`)

Add or modify arms by editing the `(system_prompt, user_template)` pairs:

* **Injector:** `bounds-relax`, `access-slip`, `init-bypass`, `reentrancy-window`
* **Exploiter:** `direct-call`, `approve-then-call`, `multi-tx-liquidity`
* **Detector:** `spec-phrase`, `flow-anomaly`, `swc-template`
* **Patcher:** `precondition-strengthen`, `cei-refactor`, `role-gating`

Keep outputs machine-readable:

* **Unified diff** for code edits (must include `*** Begin Patch` / `*** End Patch`).
* **JSON** for tx plans/findings.

---

## Roadmap

1. Plug in **real oracles** (compile/tests/anvil/spec).
2. Tune rewards/arms per role; add **contextual bandits** (LinUCB) when you have features.
3. Add **local search** (Best-of-N / small hill-climb) per step—still no training.
4. Later: IBR/league scheduling, CEGIS-style loops, SFT/DPO, RL/PBT.




## Original idea docs

The problem is when multiple LLM agents work in parallel and they have their evolution in parallel but not in an agentic system since they are adversaries (as agentic systems as I know them typically are collaboratory). For instance, one learns how to generate exploits and the other is trained on ground truth to avoid them or defend against them. I want to put them together in a GAN/RL regime so they can talk to eachother and learn to co-evolve. We have concrete case studies for software engineering. 



RQs: In what scenarios does this system make sense instead of individually evolving agents?
RQs: What hierarchical system is best for these?


Use case for smart contracts: 
Agent: Vulnerability injector
Agent: Exploit generator
Agent: Vulnerability detector
Agent: Patch generator
Agent: Arbiter/… (probably to not let the evolution go in weird direction/not fall into local minima like one adding dead code the other fixing it and thus learning something useless)

We can analyze and evaluate this use-case end-to-end.

