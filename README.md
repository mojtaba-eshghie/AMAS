# Cat&Mouse

Minimal, *weight-free* multi-agent skeleton for adversarial smart-contract workflows using **Portfolio + Bandits**.
Each role (Injector, Exploiter, Detector, Patcher) is just an **LLM prompt strategy**. We adapt **online** by picking the best strategy via a **multi-armed bandit**—no finetuning, no chat history, no guardrails.

---

## Goal

Build a practical starting point for your “Cat & Mouse” ecosystem **without** heavy training loops:

* **No SFT/RL** to start.
* **No conversation history**; each step is single-turn.
* **Online adaptation via bandits** that choose among a small **portfolio of prompts/decoding strategies** per role.
* Pluggable **programmatic oracles** (compile/tests/anvil/specs) provide a numeric reward in `[0,1]`.

---

## What we decided to build

**Option 1: Portfolio + Bandits**

* For each agent/role we keep a **portfolio** of prompt templates (the “arms”).
* After each trial, we compute a **reward** with your oracles (e.g., exploit success, patch validity).
* A **bandit policy** (UCB1 / Thompson / EXP3) updates its belief and selects the next arm.
* Adaptation happens **at inference time**; **no model weights are updated**.

---

## Current state

✅ **Implemented**

* **Bandit policies:** `UCB1`, `ThompsonBernoulli`, `EXP3`.
* **Strategy portfolios:** initial arms for `injector`, `exploiter`, `detector`, `patcher`.
* **LLM providers:**

  * `stub` (fast, deterministic demo).
  * `openai` (any OpenAI-compatible `/v1/chat/completions` endpoint).
* **Controller:** single-step loop (“select → generate → score → update”).
* **Schemas:** typed artifacts (diffs, tx plans, findings).
* **Logging:** optional JSONL per role.
* **Demos:**

  * `scripts/run_demo.py` → uses stub LLM + toy oracles.
  * `scripts/run_openai_demo.py` → uses real LLM endpoint if configured.

📋 **To wire up (you)**

* Replace toy functions in `coeva/oracles.py` with **real**: compile, tests, anvil execution, spec checks, severity weighting, non-vacuity, etc.

🧭 **Out of scope (future)**

* RL / ES, self-play, population training.
* Multi-step refinement/search per step.
* Cross-role scheduling (IBR/league).
* Dataset creation & SFT/DPO.
  *(We can add these later without changing the core structure.)*

---

## Folder structure

```
coeva-lite/
├─ coeva/
│  ├─ bandits.py        # UCB1, Thompson, EXP3
│  ├─ strategies.py     # Prompt portfolios for each role
│  ├─ llm.py            # Stub + OpenAI-compatible client
│  ├─ controller.py     # Orchestrates select→generate→score→update (+ JSONL logging)
│  ├─ oracles.py        # <== Replace with your real compile/test/anvil/spec rewarders
│  ├─ schemas.py        # DiffPatch, TxPlan, Finding
│  └─ config.py         # ENV config (provider/base_url/model/timeout/logging)
├─ scripts/
│  ├─ run_demo.py       # Stub LLM + toy oracles (quick smoke test)
│  └─ run_openai_demo.py# Real LLM path if configured
└─ tests/
   └─ test_bandits.py   # Smoke tests for bandit policies
```

---

## Quickstart

### 1) Stub demo (no external model)

```bash
python scripts/run_demo.py
```

You’ll see each role pick strategies and rewards update over time.
*(Uses stub LLM + toy oracles; numbers are illustrative.)*

### 2) Real LLM (OpenAI-compatible)

```bash
export COEVA_LLM_PROVIDER=openai
export COEVA_OPENAI_BASE_URL=https://api.openai.com          # or your local server
export COEVA_OPENAI_MODEL=gpt-4o-mini                        # or local model name
export OPENAI_API_KEY=sk-...                                 # or dummy for local servers
# optional logs
export COEVA_LOG=1
export COEVA_LOG_DIR=logs

PYTHONPATH=. python scripts/run_openai_demo.py
```

**Notes**

* Any server that speaks `/v1/chat/completions` should work (OpenAI, vLLM, LM Studio, Together, Ollama w/ compat proxy, etc.).
* Exploiter/Detector prompts expect **JSON** outputs; the parser falls back gracefully if malformed.

---

## How it works (1 page)

**At each step per role:**

1. **Select an arm** with a bandit policy (e.g., UCB1).
2. **Generate** an artifact via LLM + strategy template (diff, tx plan, finding).
3. **Score** with your oracle → reward ∈ `[0,1]`.
4. **Update** the bandit statistics; optionally log JSONL.

**Design decisions**

* **No history**: each call is single-turn; the only “state” is bandit stats (counts/means) and your logs.
* **No training**: pure test-time adaptation; easy to reset/replicate.
* **Rewards first**: The oracle is the source of truth—keep it cheap but meaningful (compile/tests/spec/anvil).
* **Normalization**: reward must be clipped to `[0,1]` for stable bandit behavior.

---

## Wiring your oracles (the important part)

Edit `coeva/oracles.py`:

* `evaluate_injector(diff)`
  *Compile + unit tests + “Δ Exploitability” under your current exploiter*.
  Reward idea: `0.4 * compile_pass + 0.4 * tests_pass + 0.2 * delta_exploitability` (clip 0–1).

* `evaluate_exploiter(plan)`
  *Run on anvil; check property violation / trace to sink; consider tx count & gas.*
  Reward idea: `1.0` if exploit succeeds; else a shaped value using “distance-to-sink” − penalties for tx_count/gas.

* `evaluate_detector(finding)`
  *Compare against runtime assertions & static signals.*
  Reward idea: severity-weighted `TP − FP − FN`, rescaled to `[0,1]`.

* `evaluate_patcher(diff)`
  *Apply patch; exploit must fail; all tests/specs pass; minimal diff; non-vacuous.*
  Reward idea: base on (block_exploit ∧ tests_pass) with bonuses for small AST diff and penalties for vacuity.

---

## Configuration

* `COEVA_LLM_PROVIDER`: `stub` (default) or `openai`
* `COEVA_OPENAI_BASE_URL`: OpenAI-compatible URL (e.g., `https://api.openai.com`)
* `COEVA_OPENAI_MODEL`: model name (e.g., `gpt-4o-mini`, `llama-3-8b-instruct`)
* `OPENAI_API_KEY`: API key (or any token for local servers)
* `COEVA_LLM_TIMEOUT`: seconds (default `60`)
* `COEVA_LOG`: `1` to enable JSONL logs
* `COEVA_LOG_DIR`: directory for logs (default `logs/`)

---

## Extending the portfolio

Add/modify strategies in `coeva/strategies.py`:

* **Injector arms**: `bounds-relax`, `access-slip`, `init-bypass`, `reentrancy-window`
* **Exploiter arms**: `direct-call`, `approve-then-call`, `multi-tx-liquidity`
* **Detector arms**: `spec-phrase`, `flow-anomaly`, `swc-template`
* **Patcher arms**: `precondition-strengthen`, `cei-refactor`, `role-gating`

Each arm is just a *(system prompt, user template)* pair. Keep outputs machine-readable: **unified diff** for code edits, **JSON** for tx plans/findings.

---

## Roadmap

1. **Replace toy oracles** with your actual harness (compile/tests/anvil/specs).
2. **Per-role tuning** of rewards and strategy portfolios.
3. Optional: **contextual bandits** (features → LinUCB) once you can extract task features (contract size, #external calls, ERC patterns).
4. Optional next rung: **local search** (Best-of-N / small hill-climb) per step—still no training.
5. Later: IBR/league scheduling, CEGIS-style loops, SFT/DPO, RL/PBT.

---

## FAQ

**Are we using a real LLM?**

* By default, **no** (stub). Set `COEVA_LLM_PROVIDER=openai` + endpoint/model to use a real one.

**Are we “learning”?**

* Yes, at **test time** via bandit arm selection. **No weight updates** occur.

**Why `[0,1]` rewards?**

* Bandits assume bounded rewards; normalize and clip for stability.

**Can I persist bandit state?**

* We log JSONL; if you want persistent bandit stats, serialize `counts`/`means` in the controller.




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

